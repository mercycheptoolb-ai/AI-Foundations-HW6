"""Problem 4: run the agent on all 12 practice documents with and without the prompt cache.

Usage:
    python cache_test.py

Writes output/cache_test.json: every model call from both setups (setup, document, every token count the
API reports, and dollars from data/prices.json), plus the per-document answers and a check that each
setup really did what it claims.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from agent import MODEL_NAME, OUTPUT, PRICES, run

HERE = Path(__file__).resolve().parent
DOCS = sorted((HERE / "data" / "practice_docs").iterdir())
KEY = {row["file"]: row for row in json.loads((HERE / "data" / "practice_key.json").read_text())}
FIELDS = ["vendor", "sku", "unit_price", "lead_time_days", "min_order", "decision"]
SETUPS = {"with_cache": "on", "without_cache": "off"}


def main() -> None:
    calls, runs = [], []
    for setup, cache in SETUPS.items():  # with_cache first, so without_cache runs while a warm cache exists
        for doc in DOCS:
            # Problem 4 setup: the Problem 3 agent (prompt rules only), before the Problem 6 defenses existed.
            answer, doc_calls = run(doc, cache, frozenset({"prompt"}))
            expected = KEY[doc.name]
            wrong = [f for f in FIELDS if getattr(answer, f) != expected[f]]
            runs.append({"setup": setup, "document": doc.name, "answer": answer.model_dump(), "wrong_fields": wrong})
            for c in doc_calls:
                calls.append({"setup": setup, "document": doc.name, **c})
            total = sum(c["cost_usd"]["total"] for c in doc_calls)
            cached = sum(c["cached_input_tokens"] for c in doc_calls)
            print(f"{setup:14} {doc.name:28} {answer.decision:17} cached={cached:>6,}  ${total:.6f}  "
                  f"{'OK' if not wrong else 'WRONG ' + ','.join(wrong)}")

    off = [c for c in calls if c["setup"] == "without_cache"]
    on = [c for c in calls if c["setup"] == "with_cache"]
    checks = {
        "without_cache_calls_with_cached_tokens": sum(c["cached_input_tokens"] > 0 for c in off),
        "with_cache_calls_with_cached_tokens": sum(c["cached_input_tokens"] > 0 for c in on),
        "with_cache_calls": len(on),
        "without_cache_calls": len(off),
    }
    assert checks["without_cache_calls_with_cached_tokens"] == 0, "without-cache run read from the cache"

    (OUTPUT / "cache_test.json").write_text(json.dumps({
        "model": MODEL_NAME,
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "prices_per_1m": json.loads(PRICES.read_text())[MODEL_NAME],
        "checks": checks,
        "calls": calls,
        "runs": runs,
    }, indent=2) + "\n")
    print("\nchecks:", checks)


if __name__ == "__main__":
    main()
