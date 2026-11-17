# -*- coding: utf-8 -*-
"""M3 价格追踪 测试（tracking.py + services/alerts.py）

覆盖目标：追踪增删查、价格走势、降价提醒（站内消息）、目标价比对生成逻辑的
语句与条件覆盖。
"""
from datetime import datetime, timedelta

from conftest import (
    auth_headers,
    make_alert,
    make_listing,
    make_product,
    make_snapshot,
    make_tracking,
    make_user,
)

from app.models import Alert, Tracking
from app.services.alerts import check_price_alerts


def _user_product(db):
    u = make_user(db, username="u3", email="u3@qq.com")
    p = make_product(db, name="追踪手机", category="手机")
    return u, p


# ================= 添加追踪 =================

def test_add_tracking_success_no_target(client, db):
    u, p = _user_product(db)
    r = client.post("/api/tracking", json={"product_id": p.id},
                    headers=auth_headers(u))
    assert r.status_code == 200 and "已加入价格追踪" in r.json()["message"]
    # target_price 为 None -> 不校验目标价的条件分支
    assert db.query(Tracking).filter(Tracking.user_id == u.id).count() == 1


def test_add_tracking_with_valid_target(client, db):
    u, p = _user_product(db)
    r = client.post("/api/tracking", json={"product_id": p.id, "target_price": 88.0},
                    headers=auth_headers(u))
    assert r.status_code == 200
    assert db.query(Tracking).first().target_price == 88.0


def test_add_tracking_product_404(client, db):
    u, _ = _user_product(db)
    r = client.post("/api/tracking", json={"product_id": 99999}, headers=auth_headers(u))
    assert r.status_code == 404 and "商品不存在" in r.json()["detail"]


def test_add_tracking_exists_update_target(client, db):
    # 已存在 + 新目标价 -> 更新目标价分支
    u, p = _user_product(db)
    make_tracking(db, u, p, target_price=90.0)
    r = client.post("/api/tracking", json={"product_id": p.id, "target_price": 70.0},
                    headers=auth_headers(u))
    assert r.status_code == 200 and "已在追踪中" in r.json()["message"]
    assert db.query(Tracking).first().target_price == 70.0


def test_add_tracking_exists_no_target_keeps_old(client, db):
    # 已存在 + 无目标价 -> 不修改目标价分支
    u, p = _user_product(db)
    make_tracking(db, u, p, target_price=90.0)
    r = client.post("/api/tracking", json={"product_id": p.id}, headers=auth_headers(u))
    assert r.status_code == 200
    assert db.query(Tracking).first().target_price == 90.0


def test_add_tracking_target_invalid(client, db):
    # 目标价 <= 0 -> 400（is not None 为真 且 <=0 为真）
    u, p = _user_product(db)
    for bad in (0, -1.5):
        r = client.post("/api/tracking", json={"product_id": p.id, "target_price": bad},
                        headers=auth_headers(u))
        assert r.status_code == 400 and "目标价格" in r.json()["detail"]


def test_add_tracking_limit_reached(client, db):
    # 数量上限条件为真 -> 400
    u, _ = _user_product(db)
    for i in range(30):
        p = make_product(db, name=f"批量商品{i}", category="数码")
        make_tracking(db, u, p)
    p31 = make_product(db, name="第31个", category="数码")
    r = client.post("/api/tracking", json={"product_id": p31.id}, headers=auth_headers(u))
    assert r.status_code == 400 and "上限" in r.json()["detail"]


# ================= 追踪列表 =================

def test_list_trackings_ok(client, db):
    u, p = _user_product(db)
    l = make_listing(db, p, current_price=100.0)
    make_listing(db, p, platform="taobao", url="https://t/1", current_price=120.0)
    make_snapshot(db, l, 100.0, datetime.now())
    make_tracking(db, u, p, target_price=90.0)
    r = client.get("/api/tracking", headers=auth_headers(u))
    assert r.status_code == 200
    item = r.json()[0]
    assert item["product_name"] == "追踪手机"
    assert item["current_price"] == 100.0 and item["created_at"] is not None


def test_list_trackings_no_priced_listing_and_null_created_at(client, db):
    # 无有效报价 -> current_price None；created_at 为空 -> None 分支
    u, p = _user_product(db)
    t = make_tracking(db, u, p)
    t.created_at = None
    db.commit()
    r = client.get("/api/tracking", headers=auth_headers(u))
    item = r.json()[0]
    assert item["current_price"] is None and item["created_at"] is None


def test_list_trackings_empty(client, db):
    u, _ = _user_product(db)
    assert client.get("/api/tracking", headers=auth_headers(u)).json() == []


# ================= 删除追踪 =================

def test_remove_tracking_ok(client, db):
    u, p = _user_product(db)
    t = make_tracking(db, u, p)
    r = client.delete(f"/api/tracking/{t.id}", headers=auth_headers(u))
    assert r.status_code == 200 and r.json()["ok"] is True
    assert db.query(Tracking).count() == 0


def test_remove_tracking_404(client, db):
    u, _ = _user_product(db)
    r = client.delete("/api/tracking/99999", headers=auth_headers(u))
    assert r.status_code == 404


def test_remove_tracking_forbidden_other_user(client, db):
    # t.user_id != user.id 为真 且 非 admin -> 403
    u1, p = _user_product(db)
    u2 = make_user(db, username="u3b", email="u3b@qq.com")
    t = make_tracking(db, u1, p)
    r = client.delete(f"/api/tracking/{t.id}", headers=auth_headers(u2))
    assert r.status_code == 403 and "无权" in r.json()["detail"]


def test_remove_tracking_admin_removes_other(client, db):
    # owner 不匹配 但 admin -> 与条件的第二个操作数为假，允许删除
    u1, p = _user_product(db)
    admin = make_user(db, username="adm3", email="adm3@qq.com", role="admin")
    t = make_tracking(db, u1, p)
    r = client.delete(f"/api/tracking/{t.id}", headers=auth_headers(admin))
    assert r.status_code == 200


# ================= 价格走势 =================

def _seed_snapshots(db, p):
    l1 = make_listing(db, p, platform="jd", url="https://j/1", current_price=100.0)
    l2 = make_listing(db, p, platform="taobao", url="https://t/1", current_price=95.0)
    base = datetime(2026, 6, 1, 10, 0)
    # 同一天多条：新日期、同日更高价、同日更低价三个分支
    make_snapshot(db, l1, 100.0, base)
    make_snapshot(db, l1, 120.0, base + timedelta(hours=1))
    make_snapshot(db, l2, 90.0, base + timedelta(hours=2))
    make_snapshot(db, l2, 95.0, base + timedelta(days=1))
    return l1, l2


def test_trend_ok_with_platform_filter(client, db):
    u, p = _user_product(db)
    _seed_snapshots(db, p)
    r = client.get(f"/api/tracking/trend/{p.id}", params={"days": 365, "platform": "jd"},
                   headers=auth_headers(u))
    data = r.json()
    assert data["product_name"] == "追踪手机"
    # 平台过滤条件为真：只留 jd 的快照，按天取最低
    assert data["points"] == [
        {"date": "2026-06-01", "price": 100.0, "platform": "jd"},
    ]
    assert data["min_price"] == 100.0 and data["max_price"] == 100.0 and data["avg_price"] == 100.0
    assert data["current_price"] == 95.0


def test_trend_ok_no_platform_filter(client, db):
    # 平台过滤条件为假：跨平台按天最低价
    u, p = _user_product(db)
    _seed_snapshots(db, p)
    data = client.get(f"/api/tracking/trend/{p.id}", params={"days": 365}).json()
    assert [pt["price"] for pt in data["points"]] == [90.0, 95.0]
    assert data["points"][0]["platform"] == "taobao"


def test_trend_no_snapshots(client, db):
    # 空序列 -> min/max/avg 为 None 的条件分支；无报价 -> current None
    u, p = _user_product(db)
    data = client.get(f"/api/tracking/trend/{p.id}").json()
    assert data["points"] == []
    assert data["min_price"] is None and data["max_price"] is None and data["avg_price"] is None
    assert data["current_price"] is None


def test_trend_product_404(client, db):
    u, _ = _user_product(db)
    r = client.get("/api/tracking/trend/99999", headers=auth_headers(u))
    assert r.status_code == 404


def test_trend_days_boundary(client, db):
    u, p = _user_product(db)
    # days 边界：低于下限 422，等于下限通过
    assert client.get(f"/api/tracking/trend/{p.id}", params={"days": 6}).status_code == 422
    assert client.get(f"/api/tracking/trend/{p.id}", params={"days": 7}).status_code == 200


# ================= 降价提醒（站内消息） =================

def test_my_alerts_all_and_unread(client, db):
    u, p = _user_product(db)
    make_alert(db, u, p, is_read=True, message="已读提醒")
    make_alert(db, u, None, is_read=False, message="无商品提醒")  # product 为空 -> 名称 "" 分支
    r_all = client.get("/api/tracking/alerts", headers=auth_headers(u))
    assert len(r_all.json()) == 2
    r_unread = client.get("/api/tracking/alerts", params={"unread_only": True},
                          headers=auth_headers(u))
    items = r_unread.json()
    assert len(items) == 1
    assert items[0]["product_name"] == "" and items[0]["message"] == "无商品提醒"


def test_mark_read_own(client, db):
    u, p = _user_product(db)
    a = make_alert(db, u, p)
    r = client.post(f"/api/tracking/alerts/{a.id}/read", headers=auth_headers(u))
    assert r.status_code == 200
    assert db.query(Alert).get(a.id).is_read is True


def test_mark_read_not_found_is_noop(client, db):
    # a 为空 -> 不报错直接返回（条件短路分支）
    u, _ = _user_product(db)
    r = client.post("/api/tracking/alerts/99999/read", headers=auth_headers(u))
    assert r.status_code == 200 and r.json()["ok"] is True


def test_mark_read_other_user_is_noop(client, db):
    # a 存在但 user 不匹配 -> 不修改（条件后半段为假）
    u1, p = _user_product(db)
    u2 = make_user(db, username="u3c", email="u3c@qq.com")
    a = make_alert(db, u1, p)
    r = client.post(f"/api/tracking/alerts/{a.id}/read", headers=auth_headers(u2))
    assert r.status_code == 200
    assert db.query(Alert).get(a.id).is_read is False


def test_mark_all_read(client, db):
    u, p = _user_product(db)
    make_alert(db, u, p, is_read=False)
    make_alert(db, u, p, is_read=False)
    assert client.post("/api/tracking/alerts/read-all", headers=auth_headers(u)).status_code == 200
    assert db.query(Alert).filter(Alert.is_read == False).count() == 0  # noqa: E712


# ================= check_price_alerts 服务（目标价比对） =================

def test_alerts_created_when_price_meets_target(client, db):
    # price == target（不满足 > 条件）-> 生成提醒
    u, p = _user_product(db)
    make_listing(db, p, current_price=90.0)
    make_tracking(db, u, p, target_price=90.0)
    n = check_price_alerts(db)
    assert n == 1
    a = db.query(Alert).first()
    assert "降价提醒" in a.message and a.price == 90.0 and a.target_price == 90.0


def test_alerts_price_above_target_skipped(client, db):
    # price > target -> continue
    u, p = _user_product(db)
    make_listing(db, p, current_price=95.0)
    make_tracking(db, u, p, target_price=90.0)
    assert check_price_alerts(db) == 0
    assert db.query(Alert).count() == 0  # created=0 -> 不 commit 的分支


def test_alerts_price_none_skipped(client, db):
    # 无任何报价 -> min 为 None -> continue
    u, p = _user_product(db)
    make_tracking(db, u, p, target_price=90.0)
    assert check_price_alerts(db) == 0


def test_alerts_duplicate_same_day_skipped(client, db):
    # 当天已有提醒 -> 去重分支
    u, p = _user_product(db)
    make_listing(db, p, current_price=80.0)
    make_tracking(db, u, p, target_price=90.0)
    assert check_price_alerts(db) == 1
    assert check_price_alerts(db) == 0
    assert db.query(Alert).count() == 1


def test_alerts_no_target_price_excluded(client, db):
    # target_price 为 None 的订阅不参与比对（查询过滤）
    u, p = _user_product(db)
    make_listing(db, p, current_price=80.0)
    make_tracking(db, u, p, target_price=None)
    assert check_price_alerts(db) == 0
