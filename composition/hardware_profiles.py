"""Derive runtime GPIO/SPI CSVs from one canonical binding and scalar overrides."""
from __future__ import annotations

import csv
import io
import os
import tempfile
from fnmatch import fnmatchcase
from pathlib import Path


def read_table(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames
        rows = list(reader)
    if not fields or len(set(fields)) != len(fields) or "name" not in fields:
        raise ValueError(f"Invalid hardware CSV header: {path}")
    names = set()
    for row in rows:
        if set(row) != set(fields) or any(value is None for value in row.values()):
            raise ValueError(f"Invalid hardware CSV row: {path}")
        if not row["name"] or row["name"] in names:
            raise ValueError(f"Missing or duplicate hardware name: {path}")
        names.add(row["name"])
    return fields, rows


def generate(source, overrides, destination):
    """Preserve binding rows; apply named field changes without editing sources.

    Override CSV columns: table,name,field,value. Names accept shell-style glob
    patterns, so a shared policy can apply to several inputs in one row.
    Unknown tables, names/fields and overlapping edits fail before output writes.
    """
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError("Generated hardware must not overlap canonical input")
    tables = {name: read_table(source / (name + ".csv")) for name in ("gpio", "spi")}
    with Path(overrides).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["table", "name", "field", "value"]:
            raise ValueError("Hardware overrides require table,name,field,value columns")
        changes = list(reader)
    edited = set()
    for change in changes:
        if set(change) != {"table", "name", "field", "value"} or any(value is None for value in change.values()):
            raise ValueError("Invalid hardware override row")
        table, pattern, field, value = (change[key] for key in ("table", "name", "field", "value"))
        if table not in tables:
            raise ValueError(f"Unknown hardware override table: {table}")
        fields, rows = tables[table]
        if field == "name" or field not in fields:
            raise ValueError(f"Unknown or immutable hardware override field: {field}")
        matches = [row for row in rows if fnmatchcase(row["name"], pattern)]
        if not matches:
            raise ValueError(f"Hardware override name matched no rows: {pattern}")
        for row in matches:
            key = table, row["name"], field
            if key in edited:
                raise ValueError(f"Overlapping hardware overrides: {key}")
            edited.add(key)
            row[field] = value
    # Finish validation before creating any output; replace individual CSVs atomically.
    destination.mkdir(parents=True, exist_ok=True)
    for table, (fields, rows) in tables.items():
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        text = buffer.getvalue()
        target = destination / (table + ".csv")
        if target.exists() and target.read_text(encoding="utf-8") == text:
            continue
        fd, temporary = tempfile.mkstemp(prefix="." + table + "-", dir=destination)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
                stream.write(text)
            os.replace(temporary, target)
        finally:
            Path(temporary).unlink(missing_ok=True)
    return destination
