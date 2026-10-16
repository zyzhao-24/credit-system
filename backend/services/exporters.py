"""Safe CSV/XLSX export helpers."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Sequence
from typing import Any

from flask import send_file


FORMULA_PREFIXES = ("=", "+", "-", "@")


def safe_csv_value(value: Any) -> str:
    text = "" if value is None else str(value)
    if text.startswith(FORMULA_PREFIXES):
        return f"'{text}"
    return text


def csv_file_response(filename: str, header: Sequence[Any], rows: Iterable[Sequence[Any]]):
    text_output = io.StringIO(newline="")
    writer = csv.writer(text_output)
    writer.writerow([safe_csv_value(value) for value in header])
    for row in rows:
        writer.writerow([safe_csv_value(value) for value in row])

    output = io.BytesIO(text_output.getvalue().encode("utf-8-sig"))
    output.seek(0)
    return send_file(
        output,
        mimetype="text/csv; charset=utf-8",
        as_attachment=True,
        download_name=filename,
    )
