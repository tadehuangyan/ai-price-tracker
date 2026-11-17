# -*- coding: utf-8 -*-
"""M4 价格对比 测试（compare.py）

覆盖目标：多商品多平台比价、历史价格对比、参数校验分支的语句与条件覆盖。
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.routers.compare import compare as compare_view

from conftest import make_listing, make_product, make_snapshot


def _seed(db):
    """P1：两个有价报价 + 历史快照（含同日多条）；P2：仅一个报价无历史"""
    p1 = make_product(db, name="对比手机", category="手机", image_url="img/p1")
    l1 = make_listing(db, p1, platform="jd", url="https://j/1", title="手机-京东", current_price=2000.0)
    make_listing(db, p1, platform="taobao", url="https://t/1", title="", current_price=1800.0)
    make_listing(db, p1, platform="pdd", url="https://p/1", title="手机-拼多多", current_price=None)  # 无价被过滤
    base = datetime(2026, 5, 1, 10, 0)
    make_snapshot(db, l1, 2100.0, base)
    make_snapshot(db, l1, 2050.0, base + timedelta(hours=1))  # 同日 -> 取更低
    make_snapshot(db, l1, 2200.0, base + timedelta(hours=3))  # 同日更高 -> 不更新的分支
    make_snapshot(db, l1, 1900.0, base + timedelta(days=1))
    p2 = make_product(db, name="对比耳机", category="数码", image_url="img/p2")
    make_listing(db, p2, platform="jd", url="https://j/2", title="耳机-京东", current_price=300.0)
    return p1, p2


def test_compare_two_products_full(client, db):
    p1, p2 = _seed(db)
    r = client.post("/api/compare", json={"product_ids": [p1.id, p2.id], "days": 365})
    assert r.status_code == 200
    data = r.json()
    # platforms 汇总取自过滤后的 offers（无价的 pdd 报价不计入）
    assert data["days"] == 365 and data["platforms"] == ["jd", "taobao"]
    m = next(x for x in data["products"] if x["product_id"] == p1.id)
    # 无价报价被过滤；按价格升序
    assert [o["platform"] for o in m["offers"]] == ["taobao", "jd"]
    # title 为空 -> 回退商品名 的两个分支
    assert m["offers"][0]["title"] == "对比手机" and m["offers"][1]["title"] == "手机-京东"
    assert m["lowest"]["platform"] == "taobao"
    assert m["diff"] == 200.0  # 多报价差价
    assert m["history_min"] == 1900.0 and m["history_max"] == 2050.0  # 同日取最低
    assert m["series"] == [{"date": "2026-05-01", "price": 2050.0}, {"date": "2026-05-02", "price": 1900.0}]
    assert m["current_min"] == 1800.0
    e = next(x for x in data["products"] if x["product_id"] == p2.id)
    assert e["diff"] == 0  # 单报价 -> 差价 0 分支


def test_compare_no_offers(client, db):
    # 全部报价无价 -> offers 空：lowest None / diff 0 / current_min None / 历史统计 None
    p = make_product(db, name="无价商品", category="数码")
    make_listing(db, p, current_price=None)
    r = client.post("/api/compare", json={"product_ids": [p.id]})
    m = r.json()["products"][0]
    assert m["offers"] == [] and m["lowest"] is None and m["diff"] == 0
    assert m["history_min"] is None and m["history_max"] is None and m["current_min"] is None
    assert m["series"] == []


def test_compare_duplicates_400(client, db):
    p1, _ = _seed(db)
    r = client.post("/api/compare", json={"product_ids": [p1.id, p1.id]})
    assert r.status_code == 400 and "不能重复" in r.json()["detail"]


def test_compare_missing_product_404(client, db):
    p1, _ = _seed(db)
    r = client.post("/api/compare", json={"product_ids": [p1.id, 99999]})
    assert r.status_code == 404 and "99999" in r.json()["detail"]


def test_compare_schema_limits_422(client, db):
    # 空列表与超过 5 个在 schema 层被拦截（max_length=5 / min_length=1）
    p1, p2 = _seed(db)
    assert client.post("/api/compare", json={"product_ids": []}).status_code == 422
    ids = [p1.id, p2.id] + list(range(100, 104))
    assert client.post("/api/compare", json={"product_ids": ids}).status_code == 422


def test_compare_func_over_five_400(db):
    # schema 之外的函数级防御分支（L34-35）：>5 个 -> 400
    body = SimpleNamespace(product_ids=[1, 2, 3, 4, 5, 6], days=180)
    with pytest.raises(HTTPException) as e:
        compare_view(body, db)
    assert e.value.status_code == 400 and "上限" in e.value.detail


def test_compare_days_window_filters_old_snapshots(client, db):
    # days 窗口过滤：把快照放到窗口之外
    p = make_product(db, name="窗口商品", category="数码")
    l = make_listing(db, p, current_price=500.0)
    make_snapshot(db, l, 400.0, datetime.now() - timedelta(days=300))
    make_snapshot(db, l, 450.0, datetime.now() - timedelta(days=2))
    r = client.post("/api/compare", json={"product_ids": [p.id], "days": 30})
    m = r.json()["products"][0]
    assert m["history_min"] == 450.0 and m["history_max"] == 450.0
    assert len(m["series"]) == 1
