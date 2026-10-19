"""Proposal -> human review -> recomputed preview -> explicit approval."""

import copy
import hashlib
import json

from .dataset import Error, digest, profile
from .engine import DATE_FORMATS, KINDS, transform, validate_operation


def sealed(record):
    record["digest"] = digest({k: v for k, v in record.items() if k != "digest"})
    return record


def check(record, kind=None):
    if not isinstance(record, dict) or record.get("version") != 1:
        raise Error("Unsupported workflow record")
    if kind and record.get("kind") != kind:
        raise Error("Wrong workflow record kind")
    if record.get("digest") != digest({k: v for k, v in record.items() if k != "digest"}):
        raise Error("Workflow digest mismatch")


def model_context(table, share_columns):
    if (
        not isinstance(share_columns, list)
        or len(share_columns) > 4
        or len(set(share_columns)) != len(share_columns)
        or any(c not in table.headers for c in share_columns)
    ):
        raise Error("Choose at most 4 distinct existing columns to share values")
    result = profile(table)
    for name, info in result["columns"].items():
        values = info.pop("value_counts")
        if name in share_columns:
            info["shared_values"] = [v for v in values if not v.get("truncated")]
    result.pop("suspicious_records")
    return result


def propose(table, provider=None, share_columns=None, imported=None):
    share_columns = share_columns or []
    if provider and imported is not None:
        raise Error("Choose a model or an imported recipe, not both")
    report = {
        "version": 1,
        "kind": "proposals",
        "source_sha256": table.source_sha256,
        "headers": list(table.headers),
        "profile": profile(table),
        "shared_columns": share_columns,
        "mode": provider.mode if provider else "imported_recipe" if imported is not None else "offline_rules",
        "proposals": [],
        "rejected": [],
        "errors": [],
        "model": {"calls": 0, "usage": {}},
    }
    candidates = []
    if provider:
        try:
            context = model_context(table, share_columns)
            result = provider.complete(
                {
                    "task": "suggest_cleaning",
                    "profile": context,
                    "allowed_kinds": sorted(KINDS),
                    "date_formats": sorted(DATE_FORMATS),
                    "operation_formats": {
                        "trim": {"required": ["kind", "column"]},
                        "blank_markers": {
                            "required": ["kind", "column", "markers"],
                            "markers_type": "string list",
                        },
                        "replace_exact": {
                            "required": ["kind", "column", "mapping"],
                            "mapping_type": "object of old:new strings",
                        },
                        "case": {"required": ["kind", "column", "mode"], "mode_enum": ["lower", "upper"]},
                        "date_iso": {"required": ["kind", "column", "format"]},
                        "drop_exact_duplicates": {"required": ["kind"]},
                    },
                    "schema": {
                        "type": "object",
                        "required": ["proposals"],
                        "properties": {
                            "proposals": {
                                "type": "array",
                                "maxItems": 12,
                                "items": {
                                    "type": "object",
                                    "required": ["operation", "reason"],
                                    "additionalProperties": False,
                                    "properties": {
                                        "operation": {"type": "object"},
                                        "reason": {"type": "string"},
                                    },
                                },
                            }
                        },
                    },
                    "instruction": "Suggest at most 12 useful allowed operations. Each operation must have ONLY its required parameters. "
                    "Do not infer a date locale or fill missing data. Values not shared are unknown. Never emit executable code. "
                    "For exact categorical spelling/case variants, suggest replace_exact only using observed shared values. "
                    "All suggestions require human approval; explain semantic risks. Empty proposals means abstention.",
                }
            )
            if (
                not isinstance(result, dict)
                or set(result) != {"proposals"}
                or not isinstance(result["proposals"], list)
                or len(result["proposals"]) > 12
            ):
                raise Error("Model must return a proposals list of at most 12 items")
            candidates = result["proposals"]
        except Error as exc:
            report["errors"].append(str(exc))
        report["model"] = {"calls": provider.calls, "usage": provider.usage}
    elif imported is not None:
        if (
            not isinstance(imported, dict)
            or not isinstance(imported.get("operations"), list)
            or len(imported["operations"]) > 12
        ):
            raise Error("Imported recipe needs at most 12 operations")
        candidates = [
            {"operation": op, "reason": "Imported recipe; re-review against this input and preview."}
            for op in imported["operations"]
        ]
    else:
        for column, info in report["profile"]["columns"].items():
            if info["whitespace"]:
                candidates.append(
                    {
                        "operation": {"kind": "trim", "column": column},
                        "reason": "Leading/trailing whitespace detected. Spaces can be meaningful; inspect changes.",
                    }
                )
            if info["missing_markers"]:
                candidates.append(
                    {
                        "operation": {
                            "kind": "blank_markers",
                            "column": column,
                            "markers": ["N/A", "NULL", "null"],
                        },
                        "reason": "Possible missing markers; confirm these strings are not valid category values.",
                    }
                )
        if report["profile"]["duplicate_rows"]:
            candidates.append(
                {
                    "operation": {"kind": "drop_exact_duplicates"},
                    "reason": "Identical whole records exist. Repeated transactions may be legitimate; inspect removals.",
                }
            )
        candidates = candidates[:12]
    for i, candidate in enumerate(candidates):
        try:
            if not isinstance(candidate, dict) or set(candidate) != {"operation", "reason"}:
                raise Error("Proposal needs exactly operation and reason; approval fields are forbidden")
            reason = candidate["reason"]
            if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 1000:
                raise Error("Proposal needs a bounded explanation")
            operation = copy.deepcopy(validate_operation(candidate["operation"], table.headers))
            report["proposals"].append(
                {
                    "id": f"p{i + 1}",
                    "operation": operation,
                    "reason": reason,
                    "risk": "record_deletion"
                    if operation["kind"] == "drop_exact_duplicates"
                    else "meaning_change_possible",
                }
            )
        except Error as exc:
            report["rejected"].append({"index": i, "reason": str(exc), "proposal": candidate})
    return sealed(report)


def quality(table):
    record = profile(table)
    for info in record["columns"].values():
        info.pop("value_counts")
    return record


def calculate(table, operations):
    if not isinstance(operations, list) or len(operations) > 12:
        raise Error("Recipe needs at most 12 operations")
    working = table
    steps = []
    audit_bytes = 0
    for operation in operations:
        working, delta = transform(working, operation)
        audit_bytes += len(json.dumps(delta, ensure_ascii=False).encode())
        if audit_bytes > 2_000_000:
            raise Error("Change audit exceeds 2 MB; use a smaller CSV or narrower recipe")
        steps.append(delta)
    core = {
        "source_sha256": table.source_sha256,
        "headers": list(table.headers),
        "operations": copy.deepcopy(operations),
        "steps": steps,
        "before": quality(table),
        "after": quality(working),
        "output_sha256": hashlib.sha256(working.csv_bytes()).hexdigest(),
        "output_records": list(working.records),
    }
    return core, working


def preview(table, proposal, review):
    check(proposal, "proposals")
    if proposal.get("source_sha256") != table.source_sha256 or proposal.get("headers") != list(table.headers):
        raise Error("Proposals belong to a different input")
    if (
        not isinstance(review, dict)
        or set(review) != {"proposal_digest", "reviewer", "decisions"}
        or review["proposal_digest"] != proposal["digest"]
        or not isinstance(review["reviewer"], str)
        or not 1 <= len(review["reviewer"].strip()) <= 100
        or not isinstance(review["decisions"], list)
        or len(review["decisions"]) > 12
    ):
        raise Error("Invalid review or proposal digest")
    entries = proposal.get("proposals")
    if not isinstance(entries, list) or len(entries) > 12:
        raise Error("Malformed proposal list")
    lookup = {}
    for item in entries:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or item["id"] in lookup:
            raise Error("Invalid or duplicate proposal ID")
        validate_operation(item.get("operation"), table.headers)
        lookup[item["id"]] = item
    choices = {}
    for item in review["decisions"]:
        if not isinstance(item, dict) or set(item) not in (
            {"id", "decision"},
            {"id", "decision", "operation"},
        ):
            raise Error("Invalid review decision fields")
        pid, decision = item["id"], item["decision"]
        if not isinstance(pid, str) or pid not in lookup or pid in choices:
            raise Error("Unknown or duplicate review ID")
        if not isinstance(decision, str) or decision not in {"accept", "reject", "modify"}:
            raise Error("Decision must be accept, reject or modify")
        if (decision == "modify") != ("operation" in item):
            raise Error("Only modify decisions must supply an operation")
        if decision == "modify":
            validate_operation(item["operation"], table.headers)
        choices[pid] = item
    operations = []
    for pid, original in lookup.items():
        choice = choices.get(pid, {"decision": "reject"})
        if choice["decision"] != "reject":
            operations.append(copy.deepcopy(choice.get("operation", original["operation"])))
    core, _ = calculate(table, operations)
    return sealed(
        {
            "version": 1,
            "kind": "preview",
            "proposal_digest": proposal["digest"],
            "review": copy.deepcopy(review),
            **core,
        }
    )


def approved_result(table, report, approval):
    check(report, "preview")
    if (
        not isinstance(approval, dict)
        or set(approval) != {"preview_digest", "approve", "reviewer"}
        or approval["preview_digest"] != report["digest"]
        or approval["approve"] is not True
        or not isinstance(approval["reviewer"], str)
        or not 1 <= len(approval["reviewer"].strip()) <= 100
    ):
        raise Error("Explicit approval must match the exact preview digest")
    core, result = calculate(table, report.get("operations"))
    if any(report.get(key) != value for key, value in core.items()):
        raise Error("Preview no longer matches the input, transformations, deltas or output")
    return result
