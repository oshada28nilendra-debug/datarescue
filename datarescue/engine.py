"""Finite deterministic cleaning operations; no expressions, eval or model code."""

from datetime import datetime

from .dataset import Error, Table

DATE_FORMATS = {"%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"}
KINDS = {"trim", "blank_markers", "replace_exact", "case", "date_iso", "drop_exact_duplicates"}


def validate_operation(op, headers):
    if not isinstance(op, dict) or not isinstance(op.get("kind"), str) or op["kind"] not in KINDS:
        raise Error("Unknown operation kind; arbitrary code is not supported")
    kind = op["kind"]
    keys = {"kind"} if kind == "drop_exact_duplicates" else {"kind", "column"}
    keys |= {
        "blank_markers": {"markers"},
        "replace_exact": {"mapping"},
        "case": {"mode"},
        "date_iso": {"format"},
    }.get(kind, set())
    if set(op) != keys:
        raise Error("Missing or unsupported operation parameters")
    if kind != "drop_exact_duplicates" and (not isinstance(op["column"], str) or op["column"] not in headers):
        raise Error("Operation column must match an input header")
    if kind == "blank_markers":
        markers = op["markers"]
        if (
            not isinstance(markers, list)
            or not 1 <= len(markers) <= 32
            or any(not isinstance(x, str) or len(x) > 200 for x in markers)
        ):
            raise Error("Provide 1–32 explicit missing markers")
    if kind == "replace_exact":
        mapping = op["mapping"]
        if (
            not isinstance(mapping, dict)
            or not 1 <= len(mapping) <= 50
            or any(
                not isinstance(k, str) or not isinstance(v, str) or len(k) > 200 or len(v) > 200
                for k, v in mapping.items()
            )
        ):
            raise Error("Provide 1–50 exact string replacement pairs")
    if kind == "case" and (not isinstance(op["mode"], str) or op["mode"] not in {"lower", "upper"}):
        raise Error("Case mode must be lower or upper")
    if kind == "date_iso" and (not isinstance(op["format"], str) or op["format"] not in DATE_FORMATS):
        raise Error("Choose one supported explicit date format")
    if any("\x00" in v for v in op.get("mapping", {}).values()) or any(
        "\x00" in k for k in op.get("mapping", {})
    ):
        raise Error("NUL is not allowed in replacement values")
    return op


def transform(table, operation):
    op = validate_operation(operation, table.headers)
    kind = op["kind"]
    rows, records, changes, removed, seen = [], [], [], [], set()
    invalid = 0
    index = table.headers.index(op["column"]) if "column" in op else None
    for record, row in zip(table.records, table.rows):
        if kind == "drop_exact_duplicates":
            if row in seen:
                removed.append(record)
                continue
            seen.add(row)
        values = list(row)
        if index is not None:
            before = row[index]
            after = before
            if kind == "trim":
                after = before.strip()
            elif kind == "blank_markers" and before in op["markers"]:
                after = ""
            elif kind == "replace_exact":
                after = op["mapping"].get(before, before)
            elif kind == "case":
                after = before.lower() if op["mode"] == "lower" else before.upper()
            elif kind == "date_iso" and before:
                try:
                    after = datetime.strptime(before, op["format"]).date().isoformat()
                except ValueError:
                    invalid += 1
            if before != after:
                changes.append({"record": record, "column": op["column"], "before": before, "after": after})
                values[index] = after
        rows.append(tuple(values))
        records.append(record)
    output = Table(table.headers, tuple(rows), tuple(records), table.source_sha256)
    delta = {
        "changed_cells": len(changes),
        "removed_records": removed,
        "invalid_values": invalid,
        "changes": changes,
        "before_state": table.state_hash(),
        "after_state": output.state_hash(),
    }
    return output, delta
