"""Problem 8: run the final defended agent (all defenses, cache on) once on every exam document.

Usage:
    python exam_run.py

Writes output/exam_results.json, one entry per file in data/exam_docs/, straight from the agent's output
and the API's token counts. Nothing is edited by hand.
"""

from __future__ import annotations

import json
from pathlib import Path

from agent import LAYERS, OUTPUT, run
from attack_test import trap_count
from tools import TRAP_FILE

HERE = Path(__file__).resolve().parent
DOCS = sorted(p for p in (HERE / "data" / "exam_docs").iterdir() if p.suffix.lower() in {".html", ".htm", ".pdf", ".eml"})


def main() -> None:
    results = []
    for doc in DOCS:
        before = trap_count()
        answer, calls = run(doc.resolve(), "on", frozenset(LAYERS))
        new_traps = json.loads(TRAP_FILE.read_text())[before:]
        entry = {
            "file": doc.name,
            "vendor": answer.vendor,
            "sku": answer.sku,
            "unit_price": answer.unit_price,
            "lead_time_days": answer.lead_time_days,
            "min_order": answer.min_order,
            "decision": answer.decision,
            "reason": answer.reason,
            "trap_tool_called": bool(new_traps),
            "input_tokens": sum(c["input_tokens"] for c in calls),
            "cached_tokens": sum(c["cached_input_tokens"] for c in calls),
            "output_tokens": sum(c["output_tokens"] for c in calls),
            "cost_usd": round(sum(c["cost_usd"]["total"] for c in calls), 8),
        }
        results.append(entry)
        print(f"{doc.name:22} {entry['decision']:17} traps={len(new_traps)} ${entry['cost_usd']:.6f}")
    (OUTPUT / "exam_results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(f"\n{len(results)} documents, total ${sum(r['cost_usd'] for r in results):.6f}")


if __name__ == "__main__":
    main()
