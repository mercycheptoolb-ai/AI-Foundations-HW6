# HW6 — Campus Customs Vendor Desk Agent

A PydanticAI agent that reads one vendor document (HTML, PDF, or `.eml` email), pulls out the vendor, SKU, unit price, lead time, and minimum order, and decides **recommend** or **do_not_recommend** using the rules in `data/shop_handbook.md`. All AI calls use OpenAI's `gpt-6-luna` through Portkey.

**Start here:** open [`output/hw6_report.html`](output/hw6_report.html) in a browser to see every result on one page.

## Run the agent

```bash
# 1. Install (Python 3.11+)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Add your key
cp .env.example .env        # then put your PORTKEY_API_KEY in .env

# 3. Run on one vendor document (all defenses on, prompt cache on)
python agent.py --doc data/practice_docs/p01_bluehen_quote.html
```

The agent prints its answer and the run's tokens and cost. It also appends to `output/usage_log.json` and `output/audit_trail.json`.

Options:

```bash
python agent.py --doc data/practice_docs/p02_elmcity_quote.html --defenses none          # no defenses (Problem 3 agent)
python agent.py --doc data/practice_docs/p02_elmcity_quote.html --defenses code,prompt   # any mix of code, design, prompt
python agent.py --doc data/practice_docs/p02_elmcity_quote.html --cache off              # don't reuse the handbook from cache
```

## Re-run the experiments

| Problem | Command | Writes |
|---|---|---|
| 2 Handbook size | `python count_tokens.py` | (prints; see `output/handbook_estimate.md`) |
| 4 Caching | `python cache_test.py` | `output/cache_test.json` |
| 5 Attacks | `python attack_test.py` | `output/attack_results.json` |
| 6 Defenses | `python defense_test.py` | `output/defense_results.json` |
| 7 Red team | `python red_team.py` | `output/red_team.json` |
| 8 Exam | `python exam_run.py` | `output/exam_results.json` |
| 9 Report | `python make_report.py` | `output/hw6_report.html` |

## Files

- `agent.py`: entry point. Builds the agent, runs it, and logs usage and audit.
- `tools.py`: `read_document`, plus the two trap tools `send_email` and `approve_payment`. The trap tools never send or pay anything; they only log to `output/trap_calls.json`.
- `models.py`: the structured output (`VendorDecision`) and run state (`DeskDeps`).
- `prompts/prompt.md`: the agent's instructions. The handbook is added after them on every call. (The assignment's checklist calls this file `prompts.md`, but the agent loads `prompt.md`, the name from the Problem 3 spec.)
- `sanitize.py` and `rules.py`: the code-layer and design-layer defenses (Problem 6).
- `data/`: the course data (handbook, prices, practice docs and key, exam docs) plus my two red-team attacks in `data/my_attacks/`.
- `output/`: every result file and write-up, Problems 2–9.
- `AI_prompts.md`: the prompts I gave my vibe coder, one section per problem.

The real `.env` is excluded by `.gitignore`; only `.env.example` (with a placeholder) is committed.
