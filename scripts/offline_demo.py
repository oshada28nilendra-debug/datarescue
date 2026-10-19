"""Authored fixture demonstration with explicit SCRIPTED test approval, not a human."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from datarescue.cli import main as cli
from datarescue.dataset import read_json


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    args.out.mkdir(parents=True, exist_ok=False)
    source, recipe = root / "fixtures/orders.csv", root / "fixtures/recipe.json"
    assert (
        cli(["plan", "--input", str(source), "--recipe", str(recipe), "--out", str(args.out / "plan")]) == 0
    )
    proposal = read_json(args.out / "plan/proposals.json")
    review = {
        "proposal_digest": proposal["digest"],
        "reviewer": "SCRIPTED authored fixture test",
        "decisions": [{"id": p["id"], "decision": "accept"} for p in proposal["proposals"]],
    }
    (args.out / "review.json").write_text(json.dumps(review, indent=2) + "\n")
    assert (
        cli(
            [
                "preview",
                "--input",
                str(source),
                "--proposals",
                str(args.out / "plan/proposals.json"),
                "--review",
                str(args.out / "review.json"),
                "--out",
                str(args.out / "preview"),
            ]
        )
        == 0
    )
    approval = read_json(args.out / "preview/approval-template.json")
    approval.update(approve=True, reviewer="SCRIPTED authored fixture test")
    (args.out / "approval.json").write_text(json.dumps(approval, indent=2) + "\n")
    assert (
        cli(
            [
                "apply",
                "--input",
                str(source),
                "--preview",
                str(args.out / "preview/preview.json"),
                "--approval",
                str(args.out / "approval.json"),
                "--out",
                str(args.out / "export"),
            ]
        )
        == 0
    )
    subprocess.run(
        [sys.executable, "-I", str(args.out / "export/clean.py"), str(source), str(args.out / "replay.csv")],
        check=True,
        timeout=20,
    )
    assert (args.out / "replay.csv").read_bytes() == (args.out / "export/cleaned.csv").read_bytes()
    print("Offline fixture and byte-identical standalone replay passed; no model calls.")


if __name__ == "__main__":
    main()
