"""Feedback API tests: bug posts (one pending per student, editable),
missing-record applications (gated by the admin toggle; structured fields;
char-match hint; admin record-with-adjustment / reject / reopen), and
permissions.

核定记录会真实落库：活动/记录不存在则自动创建；已有记录时类别必须属于
该记录的可行类别（学生上报与管理员核定都校验）；完全相同的条目不重复
录入；取消核定自动删除对应条目。BUG 反馈常驻，活动漏录仅在管理员开启
集中活动反馈期间可提交。
"""

from backend.extensions import db as _db
from backend.models import Activity, Admin
from backend.utils.passwords import client_password_digest, hash_password_digest


def _submit_bug(client, student, content="导出 PDF 时公式显示为源码"):
    return client.post(
        "/api/student/feedback",
        json={"type": "bug", "content": content},
        headers={"Authorization": student},
    ).get_json()


def _submit_missing(client, student, **overrides):
    payload = {
        "type": "missing",
        "activity_name": "测试活动二",
        "record_name": "",
        "credits": 1.5,
        "categories": ["思想品德"],
        "evidence": "活动现场合影与签到表",
    }
    payload.update(overrides)
    return client.post(
        "/api/student/feedback", json=payload, headers={"Authorization": student}
    ).get_json()


def _set_missing_open(client, admin, open_now=True):
    return client.post(
        "/api/admin/feedback/missing_open",
        json={"open": open_now},
        headers={"Authorization": admin},
    ).get_json()


def test_bug_feedback_single_pending_and_editable(
    app, database, seed_legacy_payload, minimal_payload, login
):
    """BUG 反馈：每人仅一条待处理帖子，可修改；处理后才能再提新帖。"""
    seed_legacy_payload(minimal_payload)
    client = app.test_client()
    student = login("1001", "pass123", "student")
    admin = login("admin", "adminpass", "admin")

    assert _submit_bug(client, student)["success"] is True
    # 已有待处理 BUG 帖时不能再发新帖
    rejected = _submit_bug(client, student, "另一个问题")
    assert rejected["success"] is False

    mine = client.get("/api/student/feedback", headers={"Authorization": student}).get_json()
    assert len(mine["feedbacks"]) == 1
    fid = mine["feedbacks"][0]["feedback_id"]

    # 修改待处理帖子
    edited = client.put(
        f"/api/student/feedback/{fid}",
        json={"content": "更正：导出 PDF 时公式与表格都异常"},
        headers={"Authorization": student},
    ).get_json()
    assert edited["success"] is True
    mine = client.get("/api/student/feedback", headers={"Authorization": student}).get_json()
    assert mine["feedbacks"][0]["content"] == "更正：导出 PDF 时公式与表格都异常"

    # 管理员回复并结案；结案后不可再修改，可以再发新帖
    handled = client.post(
        f"/api/admin/feedback/{fid}/handle",
        json={"action": "reply", "reply": "已修复，请重试"},
        headers={"Authorization": admin},
    ).get_json()
    assert handled["success"] is True
    assert client.put(
        f"/api/student/feedback/{fid}",
        json={"content": "再改"},
        headers={"Authorization": student},
    ).get_json()["success"] is False
    assert _submit_bug(client, student, "新的问题")["success"] is True

    # 学生端看到处理结果
    mine = client.get("/api/student/feedback", headers={"Authorization": student}).get_json()
    done = next(f for f in mine["feedbacks"] if f["status"] == "resolved")
    assert done["reply"] == "已修复，请重试" and done["handled_by"] == "admin"


def test_missing_record_application_flow(
    app, database, seed_legacy_payload, minimal_payload, login
):
    """活动漏录：结构化字段校验；字符匹配提示；管理员核定记录或拒绝。"""
    seed_legacy_payload(minimal_payload)
    client = app.test_client()
    student = login("1001", "pass123", "student")
    admin = login("admin", "adminpass", "admin")
    assert _set_missing_open(client, admin)["success"] is True

    # 字段校验：活动名/学分/类别必填；记录仅在活动存在时可从中选择
    assert _submit_missing(client, student, activity_name="")["success"] is False
    assert _submit_missing(client, student, credits=0)["success"] is False
    assert _submit_missing(client, student, categories=[])["success"] is False
    # 活动不在系统中时不能填记录；活动存在时记录必须从中选择或不选
    assert _submit_missing(client, student, record_name="第二次记录")["success"] is False
    assert (
        _submit_missing(client, student, activity_name="测试活动", record_name="不存在的记录")[
            "success"
        ]
        is False
    )
    assert _submit_missing(client, student, evidence="")["success"] is True  # 证据可选

    # 提交成功且带上字符匹配提示（"测试活动二" 与已有活动 "测试活动" 高重合）
    assert _submit_missing(client, student)["success"] is True

    # 填写时的实时匹配接口
    matches = client.post(
        "/api/student/feedback/match",
        json={"activity_name": "测试活动二"},
        headers={"Authorization": student},
    ).get_json()["matches"]
    assert matches and matches[0]["name"] == "测试活动" and matches[0]["rate"] > 0.5

    # 学生不能访问管理端接口
    assert client.get(
        "/api/admin/feedback", headers={"Authorization": student}
    ).status_code in (401, 403)

    # 管理员列表：两条漏录待处理，带结构化字段与匹配提示
    admin_list = client.get("/api/admin/feedback", headers={"Authorization": admin}).get_json()
    assert admin_list["success"] is True and admin_list["missing_open"] is True
    assert len(admin_list["feedbacks"]) == 2
    target = next(f for f in admin_list["feedbacks"] if f["evidence"])
    assert target["activity_name"] == "测试活动二" and target["record_name"] == ""
    assert target["credits"] == 1.5 and target["categories"] == ["思想品德"]
    assert target["match_hint"] and target["match_hint"][0]["name"] == "测试活动"

    # 管理员核定：修改为合理情况并记录
    recorded = client.post(
        f"/api/admin/feedback/{target['feedback_id']}/handle",
        json={
            "action": "record",
            "reply": "已按核定情况补录",
            "adjustment": {
                "activity_name": "测试活动",
                "record_name": "第一次记录",
                "credits": 1,
                "categories": ["思想品德", "文体活动"],
            },
        },
        headers={"Authorization": admin},
    ).get_json()
    assert recorded["success"] is True

    # 核定后自动录入条目到既有记录
    with app.app_context():
        record = Activity.query.filter_by(name="测试活动").first().records[0]
        entries = [
            (entry.student_id, entry.credits, set(entry.categories))
            for entry in record.entries
        ]
    assert ("1001", 1, {"思想品德", "文体活动"}) in entries

    # 核定字段不全时拒绝
    other = next(f for f in admin_list["feedbacks"] if f["feedback_id"] != target["feedback_id"])
    assert client.post(
        f"/api/admin/feedback/{other['feedback_id']}/handle",
        json={"action": "record", "reply": "x", "adjustment": {"activity_name": "测试活动"}},
        headers={"Authorization": admin},
    ).get_json()["success"] is False

    # 拒绝另一条
    rejected = client.post(
        f"/api/admin/feedback/{other['feedback_id']}/handle",
        json={"action": "reject", "reply": "经查证并未举办该活动"},
        headers={"Authorization": admin},
    ).get_json()
    assert rejected["success"] is True

    # 学生端看到核定结果与拒绝原因
    mine = client.get("/api/student/feedback", headers={"Authorization": student}).get_json()
    by_evidence = {f["evidence"]: f for f in mine["feedbacks"]}
    done = by_evidence["活动现场合影与签到表"]
    assert done["status"] == "resolved" and done["outcome"] == "recorded"
    assert done["adjustment"]["activity_name"] == "测试活动"
    assert done["adjustment"]["credits"] == 1
    refused = by_evidence[""]
    assert refused["outcome"] == "rejected" and refused["reply"] == "经查证并未举办该活动"

    # 已处理的不能直接再处理；重新打开后可再次处理
    assert client.post(
        f"/api/admin/feedback/{target['feedback_id']}/handle",
        json={"action": "reply", "reply": "重复"},
        headers={"Authorization": admin},
    ).get_json()["success"] is False
    reopened = client.post(
        f"/api/admin/feedback/{target['feedback_id']}/handle",
        json={"action": "reopen"},
        headers={"Authorization": admin},
    ).get_json()
    assert reopened["success"] is True
    assert "对应条目已删除" in reopened["message"]
    mine = client.get("/api/student/feedback", headers={"Authorization": student}).get_json()
    again = next(f for f in mine["feedbacks"] if f["feedback_id"] == target["feedback_id"])
    assert again["status"] == "pending" and again["outcome"] == ""

    # 取消核定后对应条目被自动删除，活动与记录本身保留
    with app.app_context():
        record = Activity.query.filter_by(name="测试活动").first().records[0]
        remaining = [
            (entry.student_id, entry.credits, set(entry.categories))
            for entry in record.entries
        ]
    assert ("1001", 1, {"思想品德", "文体活动"}) not in remaining


def test_missing_gate(app, database, seed_legacy_payload, minimal_payload, login):
    """集中活动反馈开关：关闭时不能提交漏录（BUG 常驻），开启后可提交。"""
    seed_legacy_payload(minimal_payload)
    client = app.test_client()
    student = login("1001", "pass123", "student")
    admin = login("admin", "adminpass", "admin")

    # 默认关闭：漏录被拒，BUG 反馈常驻可提交
    rejected = _submit_missing(client, student)
    assert rejected["success"] is False and "集中活动反馈" in rejected["message"]
    assert _submit_bug(client, student)["success"] is True
    mine = client.get("/api/student/feedback", headers={"Authorization": student}).get_json()
    assert mine["missing_open"] is False

    # 管理员开启后可提交，两端列表都带开关状态
    opened = _set_missing_open(client, admin, True)
    assert opened["success"] is True and opened["missing_open"] is True
    assert _submit_missing(client, student)["success"] is True
    mine = client.get("/api/student/feedback", headers={"Authorization": student}).get_json()
    assert mine["missing_open"] is True
    admin_list = client.get("/api/admin/feedback", headers={"Authorization": admin}).get_json()
    assert admin_list["missing_open"] is True

    # 关闭后再次不能提交，已提交的申请不受影响
    assert _set_missing_open(client, admin, False)["missing_open"] is False
    assert _submit_missing(client, student, evidence="")["success"] is False
    mine = client.get("/api/student/feedback", headers={"Authorization": student}).get_json()
    assert len([f for f in mine["feedbacks"] if f["type"] == "missing"]) == 1


def test_record_auto_create_append_dedupe(app, database, seed_legacy_payload, minimal_payload, login):
    """核定落库细节：活动/记录自动创建、类别追加不动已有条目、相同条目去重。"""
    seed_legacy_payload(minimal_payload)
    client = app.test_client()
    student = login("1001", "pass123", "student")
    admin = login("admin", "adminpass", "admin")
    assert _set_missing_open(client, admin)["success"] is True

    # 活动与记录都不存在：上报时不填记录，核定记录时自动创建活动与记录
    assert _submit_missing(client, student, activity_name="全新活动XYZ", evidence="")[
        "success"
    ] is True
    admin_list = client.get("/api/admin/feedback", headers={"Authorization": admin}).get_json()
    item = next(f for f in admin_list["feedbacks"] if f["activity_name"] == "全新活动XYZ")
    recorded = client.post(
        f"/api/admin/feedback/{item['feedback_id']}/handle",
        json={
            "action": "record",
            "reply": "属实，已补录",
            "adjustment": {
                "activity_name": "全新活动XYZ",
                "record_name": "决赛",
                "credits": 2,
                "categories": ["文体活动", "学业发展"],
            },
        },
        headers={"Authorization": admin},
    ).get_json()
    assert recorded["success"] is True
    assert "已自动创建活动「全新活动XYZ」" in recorded["message"]
    assert "已自动创建记录「决赛」" in recorded["message"]

    with app.app_context():
        activity = Activity.query.filter_by(name="全新活动XYZ").first()
        assert activity is not None and activity.created_by == "admin"
        record = activity.records[0]
        assert record.record_name == "决赛"
        assert record.categories == ["文体活动", "学业发展"]
        assert len(record.entries) == 1

    # 已有记录：核定类别超出记录可行类别时被拒绝
    assert _submit_missing(
        client,
        student,
        activity_name="全新活动XYZ",
        record_name="决赛",
        categories=["文体活动"],
        evidence="",
    )["success"] is True
    admin_list = client.get("/api/admin/feedback", headers={"Authorization": admin}).get_json()
    item2 = next(
        f
        for f in admin_list["feedbacks"]
        if f["activity_name"] == "全新活动XYZ" and f["status"] == "pending"
    )
    rejected2 = client.post(
        f"/api/admin/feedback/{item2['feedback_id']}/handle",
        json={
            "action": "record",
            "reply": "类别以核定为准",
            "adjustment": {
                "activity_name": "全新活动XYZ",
                "record_name": "决赛",
                "credits": 1,
                "categories": ["思想品德"],
            },
        },
        headers={"Authorization": admin},
    ).get_json()
    assert rejected2["success"] is False
    assert "可行类别" in rejected2["message"]

    # 已有记录：学生上报类别超出记录可行类别时同样被拒绝
    bad_submit = _submit_missing(
        client,
        student,
        activity_name="全新活动XYZ",
        record_name="决赛",
        categories=["思想品德"],
        evidence="",
    )
    assert bad_submit["success"] is False
    assert "可行类别" in bad_submit["message"]

    # 可行类别子集可以正常核定记录
    recorded2 = client.post(
        f"/api/admin/feedback/{item2['feedback_id']}/handle",
        json={
            "action": "record",
            "reply": "属实，已补录",
            "adjustment": {
                "activity_name": "全新活动XYZ",
                "record_name": "决赛",
                "credits": 1,
                "categories": ["文体活动"],
            },
        },
        headers={"Authorization": admin},
    ).get_json()
    assert recorded2["success"] is True
    with app.app_context():
        record = Activity.query.filter_by(name="全新活动XYZ").first().records[0]
        # 记录类别保持核定创建时的值，不随已有记录的后续核定改变
        assert record.categories == ["文体活动", "学业发展"]
        first_entry = record.entries[0]
        assert set(first_entry.categories) == {"文体活动", "学业发展"}

    # 完全相同的条目（同学号/学分/类别集合）不重复录入
    assert _submit_missing(
        client,
        student,
        activity_name="测试活动",
        record_name="第一次记录",
        credits=2,
        categories=["思想品德", "学业发展"],
        evidence="",
    )["success"] is True
    admin_list = client.get("/api/admin/feedback", headers={"Authorization": admin}).get_json()
    item3 = next(
        f for f in admin_list["feedbacks"] if f["record_name"] == "第一次记录" and f["status"] == "pending"
    )
    recorded3 = client.post(
        f"/api/admin/feedback/{item3['feedback_id']}/handle",
        json={
            "action": "record",
            "reply": "已有该条目",
            "adjustment": {
                "activity_name": "测试活动",
                "record_name": "第一次记录",
                "credits": 2,
                "categories": ["思想品德", "学业发展"],
            },
        },
        headers={"Authorization": admin},
    ).get_json()
    assert recorded3["success"] is True
    assert "相同条目已存在，未重复录入" in recorded3["message"]
    with app.app_context():
        record1 = Activity.query.filter_by(name="测试活动").first().records[0]
        assert len(record1.entries) == 3  # 夹具原有 3 条，未新增

    # 核定不存在的类别被拒绝
    assert _submit_missing(
        client,
        student,
        activity_name="全新活动XYZ",
        record_name="决赛",
        categories=["学业发展"],
        evidence="",
    )["success"] is True
    admin_list = client.get("/api/admin/feedback", headers={"Authorization": admin}).get_json()
    item4 = next(
        f
        for f in admin_list["feedbacks"]
        if f["activity_name"] == "全新活动XYZ" and f["status"] == "pending"
    )
    bad = client.post(
        f"/api/admin/feedback/{item4['feedback_id']}/handle",
        json={
            "action": "record",
            "reply": "x",
            "adjustment": {
                "activity_name": "全新活动XYZ",
                "record_name": "决赛",
                "credits": 1,
                "categories": ["不存在的类别"],
            },
        },
        headers={"Authorization": admin},
    ).get_json()
    assert bad["success"] is False
    assert "类别不存在" in bad["message"]


def test_submit_category_validation_and_reopen_guards(
    app, database, seed_legacy_payload, minimal_payload, login
):
    """回归：上报校验类别存在且非空白；重开清空回复；无活动编辑权限不能取消核定。"""
    seed_legacy_payload(minimal_payload)
    client = app.test_client()
    student = login("1001", "pass123", "student")
    admin = login("admin", "adminpass", "admin")
    assert _set_missing_open(client, admin)["success"] is True

    # 不存在的类别、纯空白类别都被拒绝
    assert _submit_missing(client, student, categories=["不存在的类别"])["success"] is False
    assert _submit_missing(client, student, categories=["  "])["success"] is False

    # 开关只接受布尔值
    not_bool = client.post(
        "/api/admin/feedback/missing_open",
        json={"open": "false"},
        headers={"Authorization": admin},
    ).get_json()
    assert not_bool["success"] is False

    # 核定记录后由无活动编辑权限的管理员取消核定：被拒
    assert _submit_missing(client, student, evidence="")["success"] is True
    admin_list = client.get("/api/admin/feedback", headers={"Authorization": admin}).get_json()
    item = next(f for f in admin_list["feedbacks"] if f["type"] == "missing")
    recorded = client.post(
        f"/api/admin/feedback/{item['feedback_id']}/handle",
        json={
            "action": "record",
            "reply": "已补录",
            "adjustment": {
                "activity_name": "测试活动",
                "record_name": "第一次记录",
                "credits": 1,
                "categories": ["思想品德"],
            },
        },
        headers={"Authorization": admin},
    ).get_json()
    assert recorded["success"] is True

    with app.app_context():
        _db.session.add(
            Admin(
                admin_id="admin2",
                password_hash=hash_password_digest(client_password_digest("pass456")),
                role="admin",
                department="其他部门",
            )
        )
        _db.session.commit()
    admin2 = login("admin2", "pass456", "admin")

    forbidden = client.post(
        f"/api/admin/feedback/{item['feedback_id']}/handle",
        json={"action": "reopen"},
        headers={"Authorization": admin2},
    ).get_json()
    assert forbidden["success"] is False and "编辑权限" in forbidden["message"]
    # 状态未变、条目未删
    admin_list = client.get("/api/admin/feedback", headers={"Authorization": admin}).get_json()
    still = next(f for f in admin_list["feedbacks"] if f["feedback_id"] == item["feedback_id"])
    assert still["status"] == "resolved" and still["outcome"] == "recorded"

    # 有权限的管理员重开：条目删除，回复一并清空
    reopened = client.post(
        f"/api/admin/feedback/{item['feedback_id']}/handle",
        json={"action": "reopen"},
        headers={"Authorization": admin},
    ).get_json()
    assert reopened["success"] is True and "对应条目已删除" in reopened["message"]
    admin_list = client.get("/api/admin/feedback", headers={"Authorization": admin}).get_json()
    again = next(f for f in admin_list["feedbacks"] if f["feedback_id"] == item["feedback_id"])
    assert again["status"] == "pending" and again["reply"] == ""
