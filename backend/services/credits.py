"""Credit calculation service.

The DFS implementation intentionally mirrors the legacy algorithm in app.py.
Only data access changed: records and entries are queried in their persisted
insertion order so tie-breaking behavior remains stable after migration.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import selectinload

from backend.extensions import db
from backend.models import Activity, Category, Entry, Record, Setting


def _legacy_number(value: Any) -> int | float:
    """Render integral floats the way legacy JSON data usually rendered ints."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _total_required_credits() -> int | float:
    setting = db.session.get(Setting, "total_required_credits")
    if setting is None or setting.value in (None, ""):
        return 0
    value = float(setting.value)
    return _legacy_number(value)


def calculate_student_credits(student_id: str) -> dict[str, Any]:
    """Calculate one student's credit status using the legacy DFS semantics."""
    categories = {
        category.name: category
        for category in Category.query.order_by(Category.position.asc()).all()
    }
    total_required = _total_required_credits()

    records = (
        Record.query.join(Activity, Record.activity_id == Activity.activity_id)
        .options(
            selectinload(Record.activity),
            selectinload(Record.entries).selectinload(Entry.category_links),
        )
        .order_by(Activity.position.asc(), Record.position.asc())
        .all()
    )

    entries_data: list[dict[str, Any]] = []
    for record in records:
        activity = record.activity
        if activity is None:
            continue
        for entry in record.entries:
            if entry.student_id != student_id:
                continue
            valid_categories = [cat for cat in entry.categories if cat in categories]
            if valid_categories:
                entries_data.append(
                    {
                        "activity_name": activity.name,
                        "record_name": record.record_name,
                        "credits": entry.credits,
                        "categories": valid_categories,
                    }
                )

    if not entries_data:
        category_status = {
            name: {
                "credits": 0,
                "required": _legacy_number(category.required_credits),
                "qualified": False,
            }
            for name, category in categories.items()
        }
        return {
            "activities": [],
            "category_status": category_status,
            "total_credits": 0,
            "total_required": total_required,
            "total_qualified": False,
            "all_categories_qualified": False,
            "final_qualified": False,
        }

    best_assignment = find_best_category_assignment(entries_data, categories)

    total_credits = sum(entry["credits"] for entry in entries_data)
    category_credits = {name: 0.0 for name in categories}
    for index, entry in enumerate(entries_data):
        assigned_category = best_assignment[index]
        if assigned_category:
            category_credits[assigned_category] += entry["credits"]

    activities_detail = [
        {
            "activity_name": entry["activity_name"],
            "record_name": entry["record_name"],
            "credits": _legacy_number(entry["credits"]),
            "categories": entry["categories"],
            "assigned_category": best_assignment[index],
        }
        for index, entry in enumerate(entries_data)
    ]

    category_status: dict[str, dict[str, Any]] = {}
    all_categories_qualified = True
    for name, credits in category_credits.items():
        required = categories[name].required_credits
        qualified = credits >= required
        category_status[name] = {
            "credits": _legacy_number(credits),
            "required": _legacy_number(required),
            "qualified": qualified,
        }
        if not qualified:
            all_categories_qualified = False

    total_credits_qualified = total_credits >= total_required
    return {
        "activities": activities_detail,
        "category_status": category_status,
        "total_credits": _legacy_number(total_credits),
        "total_required": total_required,
        "total_qualified": total_credits_qualified,
        "all_categories_qualified": all_categories_qualified,
        "final_qualified": total_credits_qualified and all_categories_qualified,
    }


def find_best_category_assignment(entries: list[dict[str, Any]], categories: dict[str, Category]) -> list[str | None]:
    """Use DFS with pruning to maximize the number of qualified categories."""
    entry_count = len(entries)
    best_assignment: list[str | None] = [None] * entry_count
    best_qualified_count = -1

    def count_qualified(category_credits: dict[str, float]) -> int:
        count = 0
        for category_name, credits in category_credits.items():
            if credits >= categories[category_name].required_credits:
                count += 1
        return count

    def dfs(
        index: int,
        current_assignment: list[str | None],
        category_credits: dict[str, float],
        current_qualified: int,
    ) -> None:
        nonlocal best_assignment, best_qualified_count

        remaining = entry_count - index
        if current_qualified + remaining <= best_qualified_count:
            return

        if index == entry_count:
            qualified_count = count_qualified(category_credits)
            if qualified_count > best_qualified_count:
                best_qualified_count = qualified_count
                best_assignment = current_assignment[:]
            return

        entry = entries[index]
        sorted_categories = sorted(
            entry["categories"],
            key=lambda category: (
                category_credits[category] >= categories[category].required_credits,
                -category_credits[category],
            ),
        )

        for category in sorted_categories:
            current_assignment[index] = category
            category_credits[category] += entry["credits"]
            new_qualified = count_qualified(category_credits)
            dfs(index + 1, current_assignment, category_credits, new_qualified)
            category_credits[category] -= entry["credits"]
            current_assignment[index] = None

    initial_credits = {name: 0.0 for name in categories}
    dfs(0, [None] * entry_count, initial_credits, 0)
    return best_assignment
