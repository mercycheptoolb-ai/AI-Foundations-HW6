# Problem 2 — Size up the handbook

The Campus Customs vendor desk agent sends `data/shop_handbook.md` to `gpt-6-luna` on **every call**. This file estimates what that costs, using only the handbook (no ticket, document, instructions, or output).

## 1. Token count

**Handbook = 10,058 tokens**

How I got it:

- I ran [`count_tokens.py`](../count_tokens.py), which reads the handbook and tokenizes it with OpenAI's `tiktoken` library using the **`o200k_base`** encoding. That's the tokenizer used by the GPT-4o / GPT-5 family. OpenAI doesn't publish a separate tokenizer for `gpt-6-luna`, so `o200k_base` is the closest stand-in.
- For comparison:

| Method | Tokens |
|---|---|
| `tiktoken` o200k_base (**used**) | **10,058** |
| `tiktoken` cl100k_base (older GPT-4 tokenizer) | 10,184 |
| Rule of thumb: 28,903 characters ÷ 4 | ≈ 7,226 |

The ÷4 rule of thumb undercounts by about 28%. The handbook has many numbers, SKUs, prices, and table rows, and those split into more tokens than plain English prose. That's why I used a real tokenizer instead.

```bash
../.venv/bin/python count_tokens.py
```

## 2. Prices (`data/prices.json`, gpt-6-luna, per 1M tokens)

| Token type | $ / 1M tokens | $ / token |
|---|---|---|
| Input (uncached) | $0.10 | $0.0000001 |
| Cached input (cache read) | $0.01 | $0.00000001 |
| Cache write | $0.125 | $0.000000125 |
| Output | $0.50 | (not used: the handbook is input only) |

## 3. Cost of the handbook alone

Formula: **cost = tokens × (price per 1M ÷ 1,000,000)**

### Without caching

Every call pays the full input price for all 10,058 tokens.

- **One call:** 10,058 × $0.10 / 1,000,000 = **$0.0010058** (about 0.1¢)
- **1,000 calls:** 1,000 × $0.0010058 = **$1.0058** (about $1.01)

### With caching

The handbook is the same on every call, so it can be put first in the prompt and cached. The first call writes the cache, and every later call reads it at the cached price. (The handbook is far over the 1,024-token minimum a prompt needs before it can be cached.)

- **One call, cache write (first call):** 10,058 × $0.125 / 1,000,000 = **$0.0012573**
- **One call, cache hit (any later call):** 10,058 × $0.01 / 1,000,000 = **$0.0001006**
- **1,000 calls** = 1 cache write + 999 cache hits:
  - Write: 10,058 × $0.125 / 1M = $0.0012573
  - Reads: 999 × 10,058 × $0.01 / 1M = 999 × $0.0001006 = $0.1004794
  - **Total = $0.0012573 + $0.1004794 = $0.1017367** (about $0.10)

### Summary

| Scenario | 1 call | 1,000 calls |
|---|---|---|
| No caching | $0.0010058 | **$1.0058** |
| With caching | $0.0012573 (first call, write) / $0.0001006 (hit) | **$0.1017** |
| Savings from caching | about 90% per hit | $0.9041 (≈ 90% cheaper) |

On a single call caching costs slightly *more*, because a cache write costs 1.25× the normal input price. It pays off from the second call on, since each hit is 10× cheaper than uncached input.

## 4. Checked against the real runs in Problem 4

Full details are in [`cache_test.md`](cache_test.md).

- [x] **Prompt tokens:** Yes, they're higher. Real input is **10,967–10,970 tokens** on each first call, versus 10,058 for the handbook alone. The extra is `prompt.md` (542), the tool and output schemas, and the user message.
- [x] **Tokenizer:** tiktoken says instructions + handbook = 10,606, and the API reports 10,967 including ~361 tokens of tool schemas and message format. That's consistent, so `o200k_base` was a good stand-in for `gpt-6-luna`.
- [x] **Cached tokens:** Yes, from the second call on (23 of 24 with-cache calls). They're **not** in 128-token blocks: hits were 10,811–10,844 tokens, the whole stable prefix.
- [x] **Dollars:** Each **call** costs more than estimated ($0.0014–$0.0015 uncached, $0.00014–$0.00031 on a cache hit), because the prompt is bigger than the handbook. Each **document** takes 2 calls, so 1,000 documents cost **$2.86 without cache vs $0.38 with cache**, compared with the $1.01 vs $0.10 estimated for 1,000 handbook-only calls. Caching still saves 83–87%, against the ~90% estimate.
- [x] **Cache misses:** Confirmed, and it's worse than expected. A random id at the start of the prompt blocks every cache hit, and each call is still billed as a cache **write** (1.25× input), so busting the cache costs more than having no cache.
