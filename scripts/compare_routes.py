"""Compare legacy app.py route decorators with the refactored API surface.

Exits non-zero if a legacy /api route has no replacement, or if an unexpected
new /api route appears. Run from the project root:

    .venv/Scripts/python scripts/compare_routes.py
"""

from __future__ import annotations

import ast
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
LEGACY_APP = PROJECT_ROOT / "legacy" / "app.py"

# Interfaces deliberately removed or replaced during the refactor.
LEGACY_REMOVED = {
    # Dead endpoint in legacy: it always crashed (referenced an undefined
    # variable) and no frontend ever called it.
    ("/api/admin/questionnaire/create_activity", "POST"),
}

# Routes that exist only in the new backend.
NEW_ONLY = {
    ("/api/auth/token", "POST"),
    ("/api/auth/me", "GET"),
    ("/api/auth/logout", "POST"),
    ("/api/health", "GET"),
}

DEFAULT_METHODS = {"GET"}


def legacy_api_routes() -> set[tuple[str, str]]:
    tree = ast.parse(LEGACY_APP.read_text(encoding="utf-8"))
    routes: set[tuple[str, str]] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            func = decorator.func
            if not (
                isinstance(func, ast.Attribute)
                and func.attr == "route"
                and isinstance(func.value, ast.Name)
                and func.value.id == "app"
            ):
                continue
            if not decorator.args or not isinstance(decorator.args[0], ast.Constant):
                continue
            path = decorator.args[0].value
            if not isinstance(path, str) or not path.startswith("/api"):
                continue
            methods = set(DEFAULT_METHODS)
            for keyword in decorator.keywords:
                if keyword.arg == "methods" and isinstance(keyword.value, (ast.List, ast.Tuple)):
                    methods = {
                        element.value
                        for element in keyword.value.elts
                        if isinstance(element, ast.Constant) and isinstance(element.value, str)
                    }
            routes.update((path, method) for method in methods)
    return routes


def new_api_routes() -> set[tuple[str, str]]:
    with tempfile.TemporaryDirectory() as tmp:
        from backend import create_app

        db_path = Path(tmp) / "routes.db"
        app = create_app(DATABASE_URL=f"sqlite:///{db_path.as_posix()}")
        routes: set[tuple[str, str]] = set()
        for rule in app.url_map.iter_rules():
            if not rule.rule.startswith("/api"):
                continue
            for method in rule.methods or set():
                if method in {"HEAD", "OPTIONS"}:
                    continue
                routes.add((rule.rule, method))
        return routes


def normalize(routes: set[tuple[str, str]]) -> set[tuple[str, str]]:
    # Flask url_map renders converters; normalize for comparison.
    return {
        (path.replace("<string:", "<").replace("<uuid:", "<"), method)
        for path, method in routes
    }


def main() -> int:
    legacy = legacy_api_routes() - LEGACY_REMOVED
    new = normalize(new_api_routes())
    missing = sorted(legacy - new)
    unexpected = sorted(new - legacy - NEW_ONLY)
    report = {"missing_legacy_api": missing, "unexpected_new_api": unexpected}
    print(report)
    if missing or unexpected:
        print("Route comparison FAILED")
        return 1
    print(f"Route comparison OK: {len(legacy)} legacy API routes covered, {len(new)} new routes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
