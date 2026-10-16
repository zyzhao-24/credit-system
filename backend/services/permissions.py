"""Activity-scoped authorization helpers."""

from __future__ import annotations

from typing import Any

from backend.extensions import db
from backend.models import Activity


def check_activity_edit_permission(identity: dict[str, Any], activity_id: str) -> bool:
    activity = db.session.get(Activity, activity_id)
    if activity is None:
        return False
    return identity.get("role") == "system_admin" or identity.get("sub") in activity.allowed_editors
