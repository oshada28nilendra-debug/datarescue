"""Local plan/review/preview/approve/apply command line boundary."""

import argparse
import json
import sys
from pathlib import Path

from .dataset import Error, load_csv, profile, read_json
from .export import standalone
from .provider import Model
from .render import render
from .workflow import approved_result, preview, propose


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def write_bundle(path, files):
    # All computations finish before exclusive directory creation. No overwrite.
    path = Path(path)
    path.mkdir(mode=0o700)
    for name, value in files.items():
        with (path / name).open("xb") as handle:
            handle.write(value.encode("utf-8") if isinstance(value, str) else value)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="datarescue", description="Human-approved, reproducible CSV cleaning"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("profile", "plan", "preview", "apply"):
        p = sub.add_parser(command)
        p.add_argument("--input", required=True)
        if command != "profile":
            p.add_argument("--out", required=True, help="New directory; existing paths are never overwritten")
        if command == "plan":
            mode = p.add_mutually_exclusive_group(required=True)
            mode.add_argument("--offline", action="store_true")
            mode.add_argument("--model")
            mode.add_argument("--recipe")
            p.add_argument("--endpoint", default="http://127.0.0.1:18081/v1")
            p.add_argument("--allow-remote-model", action="store_true")
            p.add_argument("--share-column", action="append", default=[])
            p.add_argument("--model-timeout", type=float, default=120)
            p.add_argument("--max-calls", type=int, default=2)
        elif command == "preview":
            p.add_argument("--proposals", required=True)
            p.add_argument("--review", required=True)
        elif command == "apply":
            p.add_argument("--preview", required=True)
            p.add_argument("--approval", required=True)
    args = parser.parse_args(argv)
    try:
        table = load_csv(args.input)
        if args.command == "profile":
            print(json_bytes(profile(table)).decode(), end="")
            return 0
        if Path(args.out).exists() or Path(args.out).is_symlink():
            raise Error("Output directory already exists; choose a new path")
        if args.command == "plan":
            provider = (
                Model(
                    args.model,
                    endpoint=args.endpoint,
                    allow_remote=args.allow_remote_model,
                    timeout=args.model_timeout,
                    max_calls=args.max_calls,
                )
                if args.model
                else None
            )
            report = propose(
                table, provider, args.share_column, read_json(args.recipe) if args.recipe else None
            )
            review = {
                "proposal_digest": report["digest"],
                "reviewer": "local reviewer",
                "decisions": [{"id": p["id"], "decision": "reject"} for p in report["proposals"]],
            }
            files = {
                "proposals.json": json_bytes(report),
                "profile.json": json_bytes(report["profile"]),
                "review-template.json": json_bytes(review),
                "review.html": render(report),
            }
            result = 3 if report["errors"] or report["rejected"] else 0
        elif args.command == "preview":
            report = preview(table, read_json(args.proposals), read_json(args.review))
            approval = {"preview_digest": report["digest"], "approve": False, "reviewer": "local reviewer"}
            files = {
                "preview.json": json_bytes(report),
                "preview.html": render(report),
                "approval-template.json": json_bytes(approval),
            }
            result = 0
        else:
            report, approval = read_json(args.preview), read_json(args.approval)
            output = approved_result(table, report, approval)
            recipe = {
                "version": 1,
                "source_sha256": table.source_sha256,
                "operations": report["operations"],
                "output_sha256": report["output_sha256"],
                "preview_digest": report["digest"],
            }
            files = {
                "cleaned.csv": output.csv_bytes(),
                "spreadsheet.csv": output.csv_bytes(spreadsheet=True),
                "recipe.json": json_bytes(recipe),
                "clean.py": standalone(recipe),
                "quality.json": json_bytes({"before": report["before"], "after": report["after"]}),
                "audit.json": json_bytes({"preview": report, "approval": approval}),
            }
            result = 0
        write_bundle(args.out, files)
        print(f"{args.command}: wrote {args.out}")
        return result
    except (Error, OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError):
        # Avoid disclosing raw dataset content, endpoint bodies or credentials in errors.
        print(
            "Refused: invalid, stale or oversized input/configuration, unavailable model, or output path. "
            "No approval is implied; inspect the documented constraints.",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
