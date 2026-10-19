"""Problem 6: rerun all 12 practice documents with each defense layer on its own and all together.

Usage:
    python defense_test.py

Setups:
    none     the Problem 3 agent with no defenses (same as Problem 5's no_security_rules baseline)
    code     only the code layer   (sanitize.py: the model sees only what a person would see)
    design   only the design layer (dangerous tools need human sign-off; decision + reason from rules.py)
    prompt   only the prompt layer (Security rules in prompts/prompt.md)
    all      all three layers (the default for agent.py)

Each setup is warmed up with one unrecorded run first, so every measured run reads the handbook from
cache and the per-layer token/dollar differences aren't skewed by a cold cache write.

Writes output/defense_results.json: the Problem 5 shape (per document: each field vs the key, decision vs
the key, trap tool called, links/planted text in the answer) plus tokens and dollars per document.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from agent import LAYERS, OUTPUT, run
from attack_test import DOCS, check, trap_count
from tools import TRAP_FILE

SETUPS = {
    "none": frozenset(),
    "code": frozenset({"code"}),
    "design": frozenset({"design"}),
    "prompt": frozenset({"prompt"}),
    "all": frozenset(LAYERS),
}
TOKEN_KEYS = ["input_tokens", "cached_input_tokens", "cache_write_tokens", "uncached_input_tokens",
              "output_tokens", "reasoning_tokens", "total_tokens"]
COST_KEYS = ["input", "cached_input", "cache_write", "output", "total"]


def main() -> None:
    out = {"time": datetime.now(timezone.utc).isoformat(timespec="seconds"), "variants": {}}
    for name, defenses in SETUPS.items():
        run(DOCS[0], "on", defenses)  # warm-up: write this setup's prompt prefix to the cache
        rows = []
        for doc in DOCS:
            before = trap_count()
            answer, calls = run(doc, "on", defenses)
            row = check(doc, answer, json.loads(TRAP_FILE.read_text())[before:])
            row["model_calls"] = len(calls)
            row["tokens"] = {k: sum(c[k] for c in calls) for k in TOKEN_KEYS}
            row["cost_usd"] = {k: round(sum(c["cost_usd"][k] for c in calls), 8) for k in COST_KEYS}
            rows.append(row)
            wrong = [f for f, v in row["fields"].items() if not v["match"]]
            print(f"{name:7} {doc.name:28} {'FOOLED' if row['fooled'] else 'ok':6} "
                  f"decision={'ok' if row['decision']['match'] else 'WRONG'} wrong={wrong} "
                  f"leak={row['planted_text_in_answer']} in={row['tokens']['input_tokens']:,} ${row['cost_usd']['total']:.6f}")
        n = len(rows)
        out["variants"][name] = {
            "defenses": sorted(defenses),
            "summary": {
                "documents": n,
                "fooled": sum(r["fooled"] for r in rows),
                "decision_wrong": sum(not r["decision"]["match"] for r in rows),
                "field_wrong": sum(not r["all_fields_match"] for r in rows),
                "trap_tool_called": sum(r["trap_tool_called"] for r in rows),
                "link_in_answer": sum(bool(r["link_in_answer"]) for r in rows),
                "planted_text_in_answer": sum(bool(r["planted_text_in_answer"]) for r in rows),
                "avg_model_calls": round(sum(r["model_calls"] for r in rows) / n, 2),
                "avg_tokens_per_doc": {k: round(sum(r["tokens"][k] for r in rows) / n, 1) for k in TOKEN_KEYS},
                "avg_cost_usd_per_doc": {k: round(sum(r["cost_usd"][k] for r in rows) / n, 8) for k in COST_KEYS},
                "total_cost_usd": round(sum(r["cost_usd"]["total"] for r in rows), 8),
            },
            "documents": rows,
        }
        print(name, {k: v for k, v in out["variants"][name]["summary"].items() if not isinstance(v, dict)})
    (OUTPUT / "defense_results.json").write_text(json.dumps(out, indent=2) + "\n")


if __name__ == "__main__":
    main()
