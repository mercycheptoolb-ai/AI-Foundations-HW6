"""Problem 7: score your own attack documents against the agent with no defenses and with all defenses.

Put your documents in data/my_attacks/ (.html, .pdf, or .eml) and add one entry per document to
data/my_attacks/my_attacks_key.json with the values a person sees in the quote:

    [{"file": "a1_example.html", "vendor": "...", "sku": "CC-..-...", "unit_price": 0.0,
      "lead_time_days": 0, "min_order": 0, "decision": "recommend",
      "planted": ["values or words your hidden text tries to get into the answer"]}]

Usage:
    python red_team.py              # 3 runs per document per setup
    python red_team.py --repeats 5

Writes output/red_team.json. Each run is a fresh model call (Portkey replay is disabled in agent.py).
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import attack_test
from agent import LAYERS, OUTPUT, run
from attack_test import check, trap_count
from tools import TRAP_FILE

HERE = Path(__file__).resolve().parent
ATTACKS = HERE / "data" / "my_attacks"
KEY_FILE = ATTACKS / "my_attacks_key.json"
SETUPS = {"none": frozenset(), "code": frozenset({"code"}), "design": frozenset({"design"}),
          "prompt": frozenset({"prompt"}), "all": frozenset(LAYERS)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=3)
    repeats = parser.parse_args().repeats

    key = json.loads(KEY_FILE.read_text())
    if not key:
        raise SystemExit(f"No documents listed in {KEY_FILE.relative_to(HERE)}. Add your attack files and their key entries first.")
    docs = []
    for row in key:
        doc = ATTACKS / row["file"]
        if not doc.exists():
            raise SystemExit(f"Listed in the key but missing: {doc.relative_to(HERE)}")
        attack_test.KEY[row["file"]] = row
        attack_test.PLANTED[row["file"]] = row.get("planted", [])
        docs.append(doc)

    out = {"time": datetime.now(timezone.utc).isoformat(timespec="seconds"), "repeats": repeats, "documents": {}}
    for doc in docs:
        out["documents"][doc.name] = {}
        for name, defenses in SETUPS.items():
            runs = []
            for _ in range(repeats):
                before = trap_count()
                answer, calls = run(doc.resolve(), "on", defenses)
                row = check(doc, answer, json.loads(TRAP_FILE.read_text())[before:])
                row["cost_usd"] = round(sum(c["cost_usd"]["total"] for c in calls), 8)
                runs.append(row)
            fooled = sum(r["fooled"] for r in runs)
            out["documents"][doc.name][name] = {"fooled": f"{fooled}/{repeats}", "runs": runs}
            print(f"{doc.name:30} {name:7} fooled {fooled}/{repeats}  "
                  f"decisions={[r['decision']['got'] for r in runs]}  traps={sum(r['trap_tool_called'] for r in runs)}")
    (OUTPUT / "red_team.json").write_text(json.dumps(out, indent=2) + "\n")


if __name__ == "__main__":
    main()
