# Problem 4 — With and without cached tokens

I ran the vendor desk agent (`gpt-6-luna` via Portkey) on all 12 practice documents, once **with cache** and once **without cache**. That's 24 runs and 48 model calls. Every call is saved in [`cache_test.json`](cache_test.json) with its setup, document, every token count the API reports, and its dollar cost from `data/prices.json`.

```bash
python cache_test.py          # runs both setups and writes output/cache_test.json
python agent.py --doc data/practice_docs/p01_bluehen_quote.html --cache off   # one doc, no cache
```

## How each setup was built

| Setup | How | Proof from the API's token counts |
|---|---|---|
| **With cache** | The instructions and handbook are identical on every call and come first in the prompt. A fixed `prompt_cache_key` routes all calls to the same cache. | **23 of 24** calls report `cached_tokens` > 0. Only the very first call (p01, call 1) had nothing to reuse yet. Every later call read 10,811–10,844 tokens from cache. |
| **Without cache** | A fresh random `Request id: <uuid>` is placed as the **first line of the instructions on every model request**. A cache hit needs an identical prefix, so no request can ever match an earlier one. | **0 of 24** calls report `cached_tokens` > 0. `cache_test.py` asserts this and fails the run if any without-cache call shows cached tokens. |

What didn't work first: OpenAI's official off switch for gpt-5.6+ models, `prompt_cache_options: {"mode": "explicit"}`, **is ignored** by `gpt-6-luna` through Portkey. A probe with two identical requests in explicit mode still returned `cached_tokens = 10,070` on the second one. So I used the random prefix instead.

The without-cache setup ran *after* the with-cache setup, while a warm cache for the handbook already existed. It still read 0 cached tokens, so the random prefix really blocks reuse.

Both setups got **12/12 documents right on every field** against `practice_key.json`, and `trap_calls.json` is still `[]`. Caching changes cost, not answers.

## 1. Total cost, cost per document, and savings

Each document takes **2 model calls**: one to call `read_document`, and one to return the answer. That's 24 calls per setup.

| | With cache | Without cache |
|---|---|---|
| Input tokens (total) | 265,564 | 266,106 |
| — cached (read at $0.01/1M) | 249,028 | **0** |
| — cache write (at $0.125/1M) | 13,512 | 263,082 |
| — uncached input (at $0.10/1M) | 3,024 | 3,024 |
| Output tokens (at $0.50/1M) | 2,494 | 2,319 |
| **Total cost, 12 docs** | **$0.005729** | **$0.034347** |
| **Cost per document** | **$0.000477** | **$0.002862** |
| Per document once the cache is warm (p02–p12) | $0.000378 | $0.002861 |

**Percent saved with cache:**

- All 12 docs: 1 − 0.005729 / 0.034347 = **83.3%**
- Warm cache (steady state, p02–p12): 1 − 0.000378 / 0.002861 = **86.8%**

Where the with-cache money goes: $0.002490 cached reads (43%), $0.001689 cache writes (29%, mostly the one cold write on p01), $0.001247 output (22%), and $0.000302 uncached input (5%).

## 2. Real numbers vs. the Problem 2 estimate

| | Problem 2 estimate | Real (this run) | Why they differ |
|---|---|---|---|
| Handbook tokens | 10,058 (tiktoken `o200k_base`) | — | The API doesn't report the handbook separately. See the next row. |
| Prompt tokens per call | handbook only: 10,058 | **10,967–10,970** on call 1 | Real calls also carry `prompt.md` (542 tokens), a heading, the 4 tool schemas (`read_document`, `send_email`, `approve_payment`, and the output schema), and the user message. tiktoken counts instructions + handbook = **10,606**, so the remaining **~361** tokens are tool schemas and message format. The handbook estimate holds up. |
| Calls per document | 1 (assumed) | **2** | The agent sends the full prompt twice: once to call the tool, once to answer. The second call also carries the document text (+155 to +322 tokens). |
| Prompt tokens per document | 10,058 | **~22,130** | 2 calls × ~11k tokens. |
| Cached tokens on a hit | 10,058 | **10,811–10,844** | The whole stable prefix (instructions + handbook + tools) is cached, not just the handbook. The counts are **not** multiples of 128, so the "128-token block" rule I expected doesn't apply to this model. |
| Cost per call, no cache | $0.0010058 | **$0.00139–$0.00150** | Larger prompt, plus every call is billed as a **cache write** at $0.125/1M instead of $0.10/1M. See surprise #1. |
| Cost per call, cache hit | $0.0001006 | **$0.00014–$0.00031** | Larger prompt, plus output tokens ($0.50/1M) and a small cache write for the new tail of each prompt. |
| 1,000 calls, no cache | $1.0058 | $1.43 per 1,000 calls ($2.86 per 1,000 **documents**) | |
| 1,000 calls, with cache | $0.1017 | $0.24 per 1,000 calls ($0.38 per 1,000 **documents**, warm) | |
| Savings | ~90% | **83–87%** | Output tokens and the extra cache writes can't be cached, so they eat a bit of the saving. |

The token estimate was accurate. The **cost** estimate was low because the agent makes 2 calls per document and the prompt carries more than the handbook.

## 3. Projection: 1,000 documents a day for 30 days (30,000 documents)

| Setup | Cost per document | × 30,000 documents |
|---|---|---|
| **With cache** (warm, steady state) | $0.000378 | **$11.33** |
| With cache (this run's average, includes the cold start) | $0.000477 | $14.32 (upper bound) |
| **Without cache** (as measured: every call billed as a cache write) | $0.002862 | **$85.87** |
| No cache at all (if all input were billed at the plain $0.10/1M) | $0.002314 | $69.43 |

**Caching saves about $74.50 a month (≈ 87%)** at this volume. At 1,000 docs a day the cache stays warm (one document every ~86 seconds, well inside the ~30-minute cache lifetime), so the cold-start write happens only a few times a month and the steady-state number ($11.33) is the realistic one. If documents came in rare bursts with long gaps, each burst would pay a fresh cache write (~$0.0014), so the cost would drift toward the $14 row.

## 4. Surprises, and why they happen

1. **"Without cache" costs more than "no caching" would.** With the cache defeated, the without-cache setup came to $0.002862 per document. Billing all input at the plain $0.10/1M would give $0.002314, so it's about 24% higher. The model *always* writes the prompt to the cache (an automatic breakpoint I couldn't turn off), and `prices.json` charges writes at **$0.125/1M, 1.25× normal input**. With a random prefix, every call pays to write a cache entry that is never read: 263,082 write tokens with 0 reads. The lesson for real agents is that anything that changes at the start of the prompt (a timestamp, a request id, a user name before the handbook) silently puts you in this worst case.

2. **The official "turn caching off" switch did nothing.** `prompt_cache_options.mode = "explicit"` is documented as disabling the automatic breakpoint, but `gpt-6-luna` via Portkey ignored it and still served cached tokens. You can't trust a setting until the token counts confirm it. That's why this test checks `cached_tokens` instead of assuming.

3. **The handbook is sent twice per document.** A tool-using agent has at least 2 model calls: decide to call the tool, then answer. Each call resends the whole system prompt, so the per-document bill is roughly 2× the per-call estimate from Problem 2. Caching helps even *inside* one document: on the cold p01 run, call 2 already reused call 1's 10,841 tokens.

4. **The first cached call costs as much as an uncached one.** p01 call 1 with cache cost $0.001387, the same as a without-cache call, because it paid the full cache write. Caching only pays off from the second call on, which matches the Problem 2 note that a single cached call costs *more* than an uncached one.

5. **Output becomes a big share of the bill once input is cached.** Output is only 2,494 tokens (under 1% of tokens), but it's 22% of the with-cache cost, because output costs $0.50/1M, 50× the cached-input price. After caching, the next thing to optimize is a shorter `reason` and fewer reasoning tokens, not the handbook.

6. **Cached counts weren't in 128-token steps.** Hits were 10,811 and 10,841–10,844 tokens, not multiples of 128. This model caches up to its breakpoint, not in fixed blocks. The small cache writes on warm calls (30–320 tokens) are the new tail of each prompt (the document text) being written too.
