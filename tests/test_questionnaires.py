"""Questionnaire ranking, waitlist, and export tests."""

from datetime import datetime, timedelta



def test_questionnaire_waitlist_cancel_and_resubmit(app, database, seed_legacy_payload, minimal_payload, login):
    seed_legacy_payload(minimal_payload)
    client = app.test_client()
    system = login("system", "adminpass", "admin")
    student1 = login("1001", "pass123", "student")
    student2 = login("1002", "pass456", "student")

    activities = client.get("/api/admin/activities", headers={"Authorization": system}).get_json()["activities"]
    start = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
    end = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
    created = client.post(
        "/api/admin/questionnaire/create_template",
        json={
            "activity_id": activities[0]["activity_id"],
            "title": "活动报名",
            "start_time": start,
            "end_time": end,
            "max_participants": 1,
            "custom_questions": [
                {"question_type": "text", "question_text": "备注", "required": False}
            ],
        },
        headers={"Authorization": system},
    )
    assert created.status_code == 200
    questionnaire_id = created.get_json()["questionnaire_id"]

    first = client.post(
        "/api/student/questionnaire/submit",
        json={"questionnaire_id": questionnaire_id, "intended_category": "思想品德", "custom_answers": {}},
        headers={"Authorization": student1},
    )
    second = client.post(
        "/api/student/questionnaire/submit",
        json={"questionnaire_id": questionnaire_id, "intended_category": "学业发展", "custom_answers": {}},
        headers={"Authorization": student2},
    )
    assert first.get_json()["success"] is True
    assert second.get_json()["success"] is True

    mine2 = client.get("/api/student/questionnaires/my_registrations", headers={"Authorization": student2}).get_json()["registrations"][0]
    assert mine2["rank"] == 2
    assert mine2["is_waitlist"] is True

    responses = client.get(
        f"/api/admin/questionnaire/responses/{questionnaire_id}", headers={"Authorization": system}
    ).get_json()["responses"]
    first_response_id = next(item["response_id"] for item in responses if item["student_id"] == "1001")
    cancelled = client.post(
        f"/api/student/questionnaire/cancel/{first_response_id}", headers={"Authorization": student1}
    )
    assert cancelled.get_json()["success"] is True

    mine2 = client.get("/api/student/questionnaires/my_registrations", headers={"Authorization": student2}).get_json()["registrations"][0]
    assert mine2["rank"] == 1
    assert mine2["is_selected"] is True

    resubmitted = client.post(
        "/api/student/questionnaire/submit",
        json={"questionnaire_id": questionnaire_id, "intended_category": "思想品德", "custom_answers": {}},
        headers={"Authorization": student1},
    )
    assert resubmitted.get_json()["success"] is True
    mine1 = client.get("/api/student/questionnaires/my_registrations", headers={"Authorization": student1}).get_json()["registrations"][0]
    assert mine1["rank"] == 2
    assert mine1["is_waitlist"] is True

    exported = client.get(
        f"/api/admin/questionnaire/responses/{questionnaire_id}/export",
        headers={"Authorization": system},
    )
    assert exported.status_code == 200
    assert exported.get_data().startswith(b"\xef\xbb\xbf")
    assert "候补".encode("utf-8") in exported.get_data()
