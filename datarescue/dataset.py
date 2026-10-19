"""Bounded CSV input and descriptive profiles. Cells always remain strings."""

import csv
import hashlib
import io
import json
import os
import re
import stat
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path


class Error(ValueError):
    pass


def digest(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def read_json(path, limit=4_000_000):
    path = Path(path)
    if path.is_symlink():
        raise Error("Symlink JSON input is not supported")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise Error("JSON input must be a regular file")
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise Error("JSON input exceeds byte limit")
    try:
        return json.loads(data)
    except (ValueError, UnicodeError):
        raise Error("Invalid JSON input") from None


@dataclass(frozen=True)
class Table:
    headers: tuple
    rows: tuple
    records: tuple
    source_sha256: str

    def csv_bytes(self, spreadsheet=False):
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer, lineterminator="\n")

        def escape(value):
            return "'" + value if spreadsheet and formula_risk(value) else value

        writer.writerow([escape(x) for x in self.headers])
        for row in self.rows:
            writer.writerow([escape(x) for x in row])
        return buffer.getvalue().encode("utf-8")

    def state_hash(self):
        return digest({"headers": self.headers, "rows": self.rows, "records": self.records})


def load_csv(path):
    path = Path(path)
    if path.is_symlink():
        raise Error("Symlink input is not supported")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise Error("Input must be a regular CSV file")
        raw = stream.read(2_000_001)
    if len(raw) > 2_000_000 or b"\x00" in raw:
        raise Error("Input is binary or exceeds 2 MB")
    try:
        decoded = raw.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(decoded, newline=""), strict=True)
        headers = next(reader)
        if (
            not 1 <= len(headers) <= 50
            or any(not x.strip() or len(x) > 200 for x in headers)
            or len(set(headers)) != len(headers)
        ):
            raise Error("Provide 1–50 nonblank unique headers of at most 200 characters")
        rows = []
        for row in reader:
            if not row and len(headers) == 1:
                row = [""]
            if len(row) != len(headers):
                raise Error("Ragged CSV record; columns must match the header")
            if any(len(x) > 4096 for x in row):
                raise Error("Cell exceeds 4096-character budget")
            rows.append(tuple(row))
            if len(rows) > 5000 or len(rows) * len(headers) > 100000:
                raise Error("CSV exceeds 5000 records or 100000 cells")
    except (UnicodeError, csv.Error, StopIteration):
        raise Error("Invalid UTF-8 comma CSV or malformed quoting") from None
    return Table(tuple(headers), tuple(rows), tuple(range(1, len(rows) + 1)), hashlib.sha256(raw).hexdigest())


def formula_risk(value):
    return value.startswith(("\t", "\r", "\n")) or value.lstrip().startswith(("=", "+", "-", "@"))


def value_type(value):
    value = value.strip()
    if not value:
        return "missing"
    if re.fullmatch(r"[+-]?\d+", value):
        return "integer_like"
    if re.fullmatch(r"[+-]?(?:\d+\.\d*|\d*\.\d+)", value):
        return "decimal_like"
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            date.fromisoformat(value)
            return "iso_date_like"
    except ValueError:
        pass
    return "text"


def profile(table):
    columns = {}
    suspicious = []
    for i, name in enumerate(table.headers):
        values = [r[i] for r in table.rows]
        types = Counter(value_type(v) for v in values)
        present_types = {k for k, n in types.items() if k != "missing" and n}
        inferred = (
            next(iter(present_types)) if len(present_types) == 1 else "mixed" if present_types else "empty"
        )
        ambiguous = 0
        for record, value in zip(table.records, values):
            match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/\d{4}", value.strip())
            if match and 1 <= int(match[1]) <= 12 and 1 <= int(match[2]) <= 12:
                ambiguous += 1
                suspicious.append({"record": record, "column": name, "reason": "ambiguous_day_month"})
            if formula_risk(value):
                suspicious.append({"record": record, "column": name, "reason": "spreadsheet_formula_prefix"})
        columns[name] = {
            "missing": types.get("missing", 0),
            "distinct": len(set(values)),
            "type_counts": dict(types),
            "inferred_type": inferred,
            "whitespace": sum(v != v.strip() for v in values),
            "leading_zero_values": sum(bool(re.fullmatch(r"0\d+", v.strip())) for v in values),
            "missing_markers": sum(v.strip() in {"N/A", "NULL", "null"} for v in values),
            "ambiguous_dates": ambiguous,
            "value_counts": [
                {"value": v[:160], "count": n, "truncated": len(v) > 160}
                for v, n in Counter(values).most_common(8)
            ],
        }
    return {
        "rows": len(table.rows),
        "columns": columns,
        "column_count": len(table.headers),
        "duplicate_rows": len(table.rows) - len(set(table.rows)),
        "formula_risk_cells": sum(formula_risk(v) for row in table.rows for v in row),
        "formula_risk_headers": sum(formula_risk(v) for v in table.headers),
        "suspicious_records": suspicious[:100],
        "suspicious_count": len(suspicious),
        "notice": "Pattern counts and inferred types are diagnostics, not proof of data correctness.",
    }
