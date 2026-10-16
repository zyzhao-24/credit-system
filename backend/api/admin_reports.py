"""Credit query, reporting, and Excel export API."""

from __future__ import annotations

import io

import openpyxl
from flask import Blueprint, g, jsonify, request, send_file
from openpyxl.styles import Alignment, Font

from backend.auth.decorators import require_admin, require_system_admin
from backend.models import Activity, Category, Student
from backend.services.credits import calculate_student_credits


admin_reports_bp = Blueprint("admin_reports", __name__)


def _error(message: str, status: int = 200, **extra):
    return jsonify({"success": False, "message": message, **extra}), status


def _student_summary(student: Student) -> dict:
    result = calculate_student_credits(student.student_id)
    return {
        "student_id": student.student_id,
        "student_name": student.name,
        "total_credits": result["total_credits"],
        "total_qualified": result["total_qualified"],
        "all_categories_qualified": result["all_categories_qualified"],
        "final_qualified": result["final_qualified"],
        "category_status": result["category_status"],
    }


@admin_reports_bp.post("/api/query/student")
@require_system_admin
def query_student():
    query = (request.get_json(silent=True) or {}).get("query", "")
    student = Student.query.filter((Student.student_id == query) | (Student.name == query)).first()
    if student is None:
        return _error("未找到该学生")
    result = calculate_student_credits(student.student_id)
    result.update({"student_id": student.student_id, "student_name": student.name, "success": True})
    return jsonify(result)


@admin_reports_bp.get("/api/admin/all_students_credits")
@require_system_admin
def all_students_credits():
    students = Student.query.order_by(Student.student_id.asc()).all()
    return jsonify({"success": True, "students": [_student_summary(student) for student in students]})


@admin_reports_bp.get("/api/admin/report")
@require_admin
def admin_report():
    is_system_admin = g.current_identity.get("role") == "system_admin"
    category_activities: dict[str, list[dict[str, str]]] = {}
    no_category_activities = []

    for activity in Activity.query.order_by(Activity.position.asc()).all():
        if not activity.categories:
            no_category_activities.append(
                {"activity_id": activity.activity_id, "activity_name": activity.name}
            )
            continue
        for category in activity.categories:
            category_activities.setdefault(category, []).append(
                {"activity_id": activity.activity_id, "activity_name": activity.name}
            )

    categories = Category.query.order_by(Category.position.asc()).all()
    category_stats = {category.name: {"qualified": 0, "unqualified": 0} for category in categories}
    total_stats = {"qualified": 0, "unqualified": 0}
    final_stats = {"qualified": 0, "unqualified": 0}
    all_students_data = []

    students = Student.query.order_by(Student.student_id.asc()).all()
    for student in students:
        result = calculate_student_credits(student.student_id)
        for category_name, status in result["category_status"].items():
            key = "qualified" if status["qualified"] else "unqualified"
            category_stats[category_name][key] += 1
        total_stats["qualified" if result["total_qualified"] else "unqualified"] += 1
        final_stats["qualified" if result["final_qualified"] else "unqualified"] += 1
        all_students_data.append(
            {
                "student_id": student.student_id,
                "student_name": student.name,
                "total_credits": result["total_credits"],
                "category_status": result["category_status"],
                "total_qualified": result["total_qualified"],
                "final_qualified": result["final_qualified"],
            }
        )

    total_students = len(students)
    for status in category_stats.values():
        status["percentage"] = round(status["qualified"] / total_students * 100, 1) if total_students else 0
    total_stats["percentage"] = round(total_stats["qualified"] / total_students * 100, 1) if total_students else 0
    final_stats["percentage"] = round(final_stats["qualified"] / total_students * 100, 1) if total_students else 0

    score_ranges = {"0-10": 0, "11-20": 0, "21-30": 0, "31-40": 0, "41-50": 0, "50+": 0}
    for item in all_students_data:
        score = item["total_credits"]
        if score <= 10:
            score_ranges["0-10"] += 1
        elif score <= 20:
            score_ranges["11-20"] += 1
        elif score <= 30:
            score_ranges["21-30"] += 1
        elif score <= 40:
            score_ranges["31-40"] += 1
        elif score <= 50:
            score_ranges["41-50"] += 1
        else:
            score_ranges["50+"] += 1

    response = {
        "success": True,
        "category_activities": category_activities,
        "no_category_activities": no_category_activities,
        "category_stats": category_stats,
        "total_stats": total_stats,
        "final_stats": final_stats,
        "score_ranges": score_ranges,
        "total_students": total_students,
        "is_system_admin": is_system_admin,
    }
    if is_system_admin:
        response["students"] = all_students_data
    return jsonify(response)


@admin_reports_bp.get("/api/admin/export")
@require_system_admin
def export_data():
    categories = Category.query.order_by(Category.position.asc()).all()
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = "学生学分统计"

    headers = ["学号", "姓名", "总学分", "总学分合格"]
    for category in categories:
        headers.extend([f"{category.name}学分", f"{category.name}合格"])
    headers.append("最终合格")
    worksheet.append(headers)
    for cell in worksheet[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")

    for student in Student.query.order_by(Student.student_id.asc()).all():
        result = calculate_student_credits(student.student_id)
        row = [
            student.student_id,
            student.name,
            result["total_credits"],
            "是" if result["total_qualified"] else "否",
        ]
        for category in categories:
            status = result["category_status"][category.name]
            row.extend([status["credits"], "是" if status["qualified"] else "否"])
        row.append("是" if result["final_qualified"] else "否")
        worksheet.append(row)

    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="学生学分统计.xlsx",
    )
