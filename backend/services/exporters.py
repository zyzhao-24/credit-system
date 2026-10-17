"""Safe CSV/XLSX export helpers."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Sequence
from typing import Any

import openpyxl
from openpyxl.styles import Alignment, Font

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


def xlsx_file_response(
    filename: str,
    sheet_title: str,
    header: Sequence[Any],
    rows: Iterable[Sequence[Any]],
):
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = sheet_title
    worksheet.append(["" if value is None else str(value) for value in header])
    for cell in worksheet[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")
    for row in rows:
        worksheet.append(["" if value is None else str(value) for value in row])

    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )
