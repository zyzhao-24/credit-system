"""Regression tests for the legacy credit-assignment semantics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from backend.services.credits import calculate_student_credits


ROOT = Path(__file__).resolve().parents[1]


def normalize_numbers(value: Any) -> Any:
    """Treat legacy JSON ints and SQL REAL integral floats as equivalent."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, list):
        return [normalize_numbers(item) for item in value]
    if isinstance(value, dict):
        return {key: normalize_numbers(item) for key, item in value.items()}
    return value


def test_credit_assignment_preserves_legacy_semantics(database, seed_legacy_payload, minimal_payload):
    counts = seed_legacy_payload(minimal_payload)
    assert counts["entries"] == 3

    result = calculate_student_credits("1001")

    assert result["total_credits"] == 3
    assert result["total_required"] == 3
    assert result["total_qualified"] is True
    assert result["all_categories_qualified"] is False
    assert result["final_qualified"] is False
    assert result["category_status"]["思想品德"] == {
        "credits": 2,
        "required": 2,
        "qualified": True,
    }
    assert result["category_status"]["学业发展"] == {
        "credits": 1,
        "required": 1,
        "qualified": True,
    }
    assert [item["assigned_category"] for item in result["activities"]] == [
        "思想品德",
        "学业发展",
    ]


def test_student_without_entries(database, seed_legacy_payload, minimal_payload):
    seed_legacy_payload(minimal_payload)

    result = calculate_student_credits("1002")

    assert result["activities"] == []
    assert result["total_credits"] == 0
    assert result["final_qualified"] is False
    assert set(result["category_status"]) == {"思想品德", "学业发展", "文体活动"}


@pytest.mark.skipif(
    not (ROOT / "var/golden/legacy_baseline.json").is_file() or not (ROOT / "data.json").is_file(),
    reason="真实数据黄金基线不存在",
)
def test_real_data_matches_legacy_golden(database, seed_legacy_payload):
    payload = json.loads((ROOT / "data.json").read_text(encoding="utf-8"))
    golden = json.loads((ROOT / "var/golden/legacy_baseline.json").read_text(encoding="utf-8"))

    counts = seed_legacy_payload(payload)
    assert counts == golden["counts"]

    for student_id, expected in golden["direct_student_credits"].items():
        actual = calculate_student_credits(student_id)
        assert normalize_numbers(actual) == normalize_numbers(expected), student_id
