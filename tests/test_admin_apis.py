"""Administration API and authorization regression tests."""

from backend.utils.passwords import client_password_digest


def test_student_list_and_otp_reset_for_system_admin(
    app, database, seed_legacy_payload, minimal_payload, login
):
    """学生列表对系统管理员附带联系方式与 OTP 状态；可重置学生 OTP（不发邮件）。"""
    seed_legacy_payload(minimal_payload)
    client = app.test_client()
    system = login("system", "adminpass", "admin")
    normal = login("admin", "adminpass", "admin")

    full = client.get("/api/admin/students", headers={"Authorization": system}).get_json()
    student_row = next(s for s in full["students"] if s["student_id"] == "1001")
    assert student_row["phone"] == "13800000000"
    assert "has_otp" in student_row

    # 普通管理员看不到联系方式
    limited = client.get("/api/admin/students", headers={"Authorization": normal}).get_json()
    assert all("phone" not in s for s in limited["students"])

    # 重置学生 OTP：一次性返回二维码与密钥
    reset = client.post(
        "/api/admin/students/reset_otp",
        json={"student_id": "1001"},
        headers={"Authorization": system},
    )
    payload = reset.get_json()
    assert payload["success"] is True
    assert payload["otp_secret"]
    assert payload["otp_qr"].startswith("data:image/png;base64,")

    # 普通管理员无权重置
    denied = client.post(
        "/api/admin/students/reset_otp",
        json={"student_id": "1001"},
        headers={"Authorization": normal},
    )
    assert denied.status_code == 403


def test_system_admin_role_is_reserved_for_builtin_account(
    app, database, seed_legacy_payload, minimal_payload, login
):
    """系统管理员固定为内置 system 账号：接口不能创建或提升 system_admin。"""
    seed_legacy_payload(minimal_payload)
    client = app.test_client()
    token = login("system", "adminpass", "admin")

    created = client.post(
        "/api/admin/admins",
        json={"admin_id": "boss", "password": "x123456", "role": "system_admin"},
        headers={"Authorization": token},
    )
    assert created.get_json()["success"] is False

    promoted = client.put(
        "/api/admin/admins",
        json={"admin_id": "admin", "role": "system_admin"},
        headers={"Authorization": token},
    )
    assert promoted.get_json()["success"] is False


def test_batch_import_does_not_reset_existing_password(app, database, seed_legacy_payload, minimal_payload, login):
    seed_legacy_payload(minimal_payload)
    client = app.test_client()
    token = login("system", "adminpass", "admin")

    response = client.post(
        "/api/admin/students/batch",
        json={"csv_data": "1001,改名学生\n2002,新学生"},
        headers={"Authorization": token},
    )
    assert response.status_code == 200
    assert response.get_json()["added"] == 1
    assert response.get_json()["updated"] == 1

    old_login = client.post(
        "/api/auth/token",
        data={
            "username": "1001",
            "password": client_password_digest("pass123"),
            "user_type": "student",
        },
    )
    assert old_login.status_code == 200


def test_activity_permission_holes_are_closed(app, database, seed_legacy_payload, minimal_payload, login):
    seed_legacy_payload(minimal_payload)
    client = app.test_client()
    system_token = login("system", "adminpass", "admin")
    normal_token = login("admin", "adminpass", "admin")

    created = client.post(
        "/api/admin/activities",
        json={"name": "系统活动", "categories": ["思想品德"], "department": "团委"},
        headers={"Authorization": system_token},
    )
    assert created.status_code == 200
    activity_id = created.get_json()["activity_id"]

    denied_delete = client.delete(
        "/api/admin/activities",
        json={"activity_id": activity_id},
        headers={"Authorization": normal_token},
    )
    assert denied_delete.status_code == 403

    record = client.post(
        "/api/admin/records",
        json={"activity_id": activity_id, "record_name": "记录"},
        headers={"Authorization": system_token},
    )
    record_id = record.get_json()["record_id"]
    entry = client.post(
        "/api/admin/entries",
        json={"record_id": record_id, "student_id": "1001", "credits": 1, "categories": ["思想品德"]},
        headers={"Authorization": system_token},
    )
    assert entry.status_code == 200
    entry_id = entry.get_json()["entry_id"]

    denied_update = client.put(
        "/api/admin/entries",
        json={"record_id": record_id, "entry_id": entry_id, "credits": 2},
        headers={"Authorization": normal_token},
    )
    denied_delete_entry = client.delete(
        "/api/admin/entries",
        json={"record_id": record_id, "entry_id": entry_id},
        headers={"Authorization": normal_token},
    )
    assert denied_update.status_code == 403
    assert denied_delete_entry.status_code == 403

    allowed = client.put(
        "/api/admin/entries",
        json={"record_id": record_id, "entry_id": entry_id, "credits": 2},
        headers={"Authorization": system_token},
    )
    assert allowed.status_code == 200


def test_record_detail_and_batch_entry_flow(app, database, seed_legacy_payload, minimal_payload, login):
    seed_legacy_payload(minimal_payload)
    client = app.test_client()
    token = login("admin", "adminpass", "admin")
    activities = client.get("/api/admin/activities", headers={"Authorization": token}).get_json()["activities"]
    activity_id = activities[0]["activity_id"]
    records = client.get(
        f"/api/admin/activities/{activity_id}/records", headers={"Authorization": token}
    ).get_json()["records"]
    record_id = records[0]["record_id"]

    batch = client.post(
        "/api/admin/entries/batch",
        json={
            "record_id": record_id,
            "entries_text": "测试学生二,1.5\n不存在姓名,1\n3001,2",
            "categories": ["文体活动"],
        },
        headers={"Authorization": token},
    )
    assert batch.status_code == 200
    payload = batch.get_json()
    assert payload["added"] == 2
    assert payload["ignored"] == 1

    detail = client.get(f"/api/admin/records/{record_id}", headers={"Authorization": token})
    entries = detail.get_json()["record"]["entries"]
    assert any(item["student_id"] == "3001" for item in entries)
    assert all("entry_id" in item for item in entries)

    deleted = client.post(
        "/api/admin/entries/batch_delete",
        json={"record_id": record_id, "student_ids": ["3001"]},
        headers={"Authorization": token},
    )
    assert deleted.get_json()["deleted"] == 1
