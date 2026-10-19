"""Real local model integration gate on an authored fixture; no accuracy benchmark.

Runs one actual request, requires a supported exact spelling repair, then records
explicit scripted test approval (NOT an actual human review), exports and replays.
Start a compatible local server separately, or use verify_local.py.
"""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from datarescue.cli import main as cli
from datarescue.dataset import load_csv
from datarescue.provider import Model
from datarescue.workflow import approved_result, preview, propose


def run(out, endpoint):
    out.mkdir(parents=True, exist_ok=False)
    source = Path(__file__).resolve().parents[1] / "fixtures/live-status.csv"
    table = load_csv(source)
    provider = Model("datarescue-qwen3", endpoint=endpoint, max_calls=1)
    proposal = propose(table, provider, ["status"])
    (out / "proposals.json").write_text(json.dumps(proposal, indent=2) + "\n")
    selected = []
    for p in proposal["proposals"]:
        op = p["operation"]
        if op["kind"] == "replace_exact" and op.get("column") == "status":
            mapping = op["mapping"]
            if mapping.get("pendng") == "pending" and all(
                (old, new)
                in {("pendng", "pending"), ("Pending", "pending"), ("pending", "pending"), ("done", "done")}
                for old, new in mapping.items()
            ):
                selected.append(p["id"])
    if proposal["errors"] or not selected:
        raise RuntimeError(
            "Real model did not produce the expected bounded spelling repair; inspect retained proposals"
        )
    review = {
        "proposal_digest": proposal["digest"],
        "reviewer": "automated authored-fixture gate, not a person",
        "decisions": [
            {"id": p["id"], "decision": "accept" if p["id"] in selected else "reject"}
            for p in proposal["proposals"]
        ],
    }
    report = preview(table, proposal, review)
    approval = {
        "preview_digest": report["digest"],
        "approve": True,
        "reviewer": "automated authored-fixture gate, not a person",
    }
    result = approved_result(table, report, approval)
    assert result.rows[1][1] == "pending"
    assert result.rows[0][0] == "001"
    assert table.rows[1][1] == "pendng"
    (out / "preview.json").write_text(json.dumps(report, indent=2) + "\n")
    (out / "approval.json").write_text(json.dumps(approval, indent=2) + "\n")
    rc = cli(
        [
            "apply",
            "--input",
            str(source),
            "--preview",
            str(out / "preview.json"),
            "--approval",
            str(out / "approval.json"),
            "--out",
            str(out / "export"),
        ]
    )
    assert rc == 0
    subprocess.run(
        [sys.executable, "-I", str(out / "export/clean.py"), str(source), str(out / "replay.csv")],
        check=True,
        timeout=20,
    )
    assert (out / "replay.csv").read_bytes() == (out / "export/cleaned.csv").read_bytes()
    evidence = {
        "result": "passed",
        "fixture": "authored fictional categorical statuses",
        "calls": provider.calls,
        "usage": provider.usage,
        "selected_ids": selected,
        "rejected_proposals": proposal["rejected"],
        "preview_digest": report["digest"],
        "output_sha256": hashlib.sha256(result.csv_bytes()).hexdigest(),
        "limitation": "One synthetic case, scripted test approval; not a general accuracy or human-usability claim.",
    }
    (out / "verification.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--endpoint", default="http://127.0.0.1:18081/v1")
    a = p.parse_args()
    run(a.out, a.endpoint)
