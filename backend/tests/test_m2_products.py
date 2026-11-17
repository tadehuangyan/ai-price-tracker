# -*- coding: utf-8 -*-
"""M2 商品价格查询 测试（products.py）

覆盖目标：搜索/分类/排序/分页、全网新发现（含缓存）、链接收录、商品详情、
实时价格查询的语句与条件覆盖。爬虫适配层在接口边界 mock。
"""
from datetime import datetime

import pytest

from app.routers import products as products_mod

from conftest import make_listing, make_product, make_snapshot


@pytest.fixture(autouse=True)
def _reset_discover_cache():
    products_mod._discover_cache.update({"at": 0.0, "items": []})
    yield
    products_mod._discover_cache.update({"at": 0.0, "items": []})


def _seed_products(db):
    """3 个商品：P1 双报价(有快照)、P2 单报价(无快照、无采集时间)、P3 无报价"""
    p1 = make_product(db, name="旗舰手机A", category="手机")
    l1 = make_listing(db, p1, platform="jd", url="https://item.jd.com/1.html",
                      title="A-京东", current_price=1999.0, last_crawled_at=datetime.now())
    make_listing(db, p1, platform="taobao", url="https://item.taobao.com/1.html",
                 title="", current_price=1899.0)
    make_snapshot(db, l1, 1999.0, datetime(2026, 1, 1, 10, 0))
    make_snapshot(db, l1, 1950.0, datetime(2026, 1, 2, 10, 0))
    p2 = make_product(db, name="机械键盘B", category="数码")
    make_listing(db, p2, platform="jd", url="https://item.jd.com/2.html",
                 title="B-京东", current_price=399.0)
    p3 = make_product(db, name="无报价商品C", category="")
    return p1, p2, p3


# ================= 搜索 =================

def test_search_default_sort_no_filter(client, db):
    _seed_products(db)
    r = client.get("/api/products/search", params={"sort": "default"})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 3 and data["page"] == 1 and len(data["items"]) == 3
    # _product_min_price 有报价/无报价两个分支
    prices = {i["name"]: i["min_price"] for i in data["items"]}
    assert prices["旗舰手机A"] == 1899.0
    assert prices["无报价商品C"] is None
    # listings 里 last_crawled_at 有值/为空两分支
    p1 = next(i for i in data["items"] if i["name"] == "旗舰手机A")
    assert p1["listings"][0]["last_crawled_at"] is not None
    assert any(l["last_crawled_at"] is None for l in p1["listings"])


def test_search_keyword_filter(client, db):
    _seed_products(db)
    r = client.get("/api/products/search", params={"keyword": "键盘"})
    assert r.json()["total"] == 1 and r.json()["items"][0]["name"] == "机械键盘B"


def test_search_category_filter(client, db):
    _seed_products(db)
    r = client.get("/api/products/search", params={"category": "手机"})
    assert r.json()["total"] == 1


def test_search_sort_random(client, db):
    _seed_products(db)
    r = client.get("/api/products/search", params={"sort": "random"})
    assert r.status_code == 200 and r.json()["total"] == 3


def test_search_sort_newest(client, db):
    _seed_products(db)
    r = client.get("/api/products/search", params={"sort": "newest"})
    ids = [i["id"] for i in r.json()["items"]]
    assert ids == sorted(ids, reverse=True)


def test_search_sort_price_asc_with_filters(client, db):
    # 价格排序分支 + keyword/category 过滤条件均为真
    _seed_products(db)
    r = client.get("/api/products/search", params={
        "sort": "price_asc", "keyword": "手机", "category": "手机",
    })
    assert r.status_code == 200 and r.json()["total"] == 1


def test_search_sort_price_asc_no_filter(client, db):
    # 价格排序分支 + keyword/category 过滤条件均为假
    _seed_products(db)
    r = client.get("/api/products/search", params={"sort": "price_asc"})
    items = r.json()["items"]
    assert [i["min_price"] for i in items if i["min_price"] is not None] == [399.0, 1899.0]


def test_search_sort_price_desc(client, db):
    # 三元表达式 price_asc ? asc : desc 的 desc 分支
    _seed_products(db)
    r = client.get("/api/products/search", params={"sort": "price_desc"})
    items = [i["min_price"] for i in r.json()["items"] if i["min_price"] is not None]
    assert items == [1899.0, 399.0]


def test_search_pagination(client, db):
    _seed_products(db)
    r = client.get("/api/products/search", params={"sort": "newest", "page": 2, "page_size": 2})
    data = r.json()
    assert data["total"] == 3 and len(data["items"]) == 1


def test_search_page_size_limit_422(client):
    r = client.get("/api/products/search", params={"page_size": 51})
    assert r.status_code == 422


def test_search_zero_price_listing_min_price_none(client, db):
    # min(current_price) 为 0 -> falsy -> 返回 None 的条件分支
    p = make_product(db, name="零价商品", category="数码")
    make_listing(db, p, current_price=0.0)
    r = client.get("/api/products/search", params={"keyword": "零价"})
    assert r.json()["items"][0]["min_price"] is None


# ================= 分类（与慢慢买保持一致） =================

def test_categories_matches_manmanbuy(client):
    r = client.get("/api/products/categories")
    cats = r.json()
    names = {c["name"] for c in cats}
    assert {"手机数码", "电脑办公", "家用电器"} <= names
    assert all("code" in c and c["code"].startswith("cf") for c in cats)


# ================= 实时慢慢买数据 =================

def test_live_search_by_keyword(client, monkeypatch):
    monkeypatch.setattr("app.services.crawler.manmanbuy.discover_products",
                        lambda keyword, limit=20: _fake_discover(keyword, limit))
    r = client.get("/api/products/live-search", params={"keyword": "手机", "n": 3})
    data = r.json()
    assert data["keyword"] == "手机"
    assert len(data["items"]) == 3
    assert all(i["kind"] == "product" for i in data["items"])


def test_live_search_by_category_and_cache(client, monkeypatch):
    calls = []
    items = [{"title": f"商品{i}", "price": 9.0, "platform": "京东商城",
              "url": f"https://cu.manmanbuy.com/discuxiao_{i}.aspx", "image": "",
              "time": "11-17 10:00", "tag": "历史新低", "kind": "deal"} for i in range(5)]

    def fake(cf_code, limit=24):
        calls.append(cf_code)
        return items[:limit]

    monkeypatch.setattr("app.services.crawler.manmanbuy.browse_category", fake)
    products_mod._live_cache.clear()
    r1 = client.get("/api/products/live-search", params={"category": "cf6", "n": 4})
    r2 = client.get("/api/products/live-search", params={"category": "cf6", "n": 4})
    assert len(calls) == 1  # 第二次命中缓存
    assert len(r1.json()["items"]) == 4 and len(r2.json()["items"]) == 4
    assert r1.json()["items"][0]["kind"] == "deal"


def test_live_product_detail(client, monkeypatch):
    fake = dict(_fake_query_history_ok("u"), deal_url="https://cu.manmanbuy.com/discuxiao_1.aspx",
                site_name="京东", history_min=90.0, history_min_date="2026-01-01")
    monkeypatch.setattr("app.services.crawler.manmanbuy.live_product", lambda url, timeout_ms=0: fake)
    r = client.get("/api/products/live", params={"url": "https://item.jd.com/x.html"})
    data = r.json()
    assert data["title"] == "抓取到的商品"
    assert data["min_price"] == 90.0 and data["max_price"] == 95.0
    assert len(data["history"]) == 2


def test_live_product_invalid_url_400(client):
    r = client.get("/api/products/live", params={"url": "javascript:alert(1)"})
    assert r.status_code == 400


# ================= 全网新发现 =================

def _fake_discover(keyword, limit=20):
    return [
        {"title": f"发现商品{i}", "price": 100.0 + i, "platform": "taobao",
         "url": f"https://new.example.com/{i}", "image": "", "keyword": keyword}
        for i in range(limit)
    ]


def test_discover_first_call_and_dedup(client, db, monkeypatch):
    # 首次调用走爬虫：缓存为空分支；命中已知 URL 被过滤；超过 20 条截断
    p = make_product(db)
    make_listing(db, p, url="https://new.example.com/0")
    monkeypatch.setattr("app.services.crawler.manmanbuy.discover_products",
                        lambda keyword, limit=20: _fake_discover(keyword, 25))
    r = client.get("/api/products/discover", params={"n": 5})
    data = r.json()
    assert len(data["items"]) == 5
    assert all(i["url"] != "https://new.example.com/0" for i in data["items"])
    assert data["keyword"] == ""  # 缓存未记录 keyword 的 .get 默认分支


def test_discover_cache_hit(client, monkeypatch):
    calls = []

    def fake(keyword, limit=20):
        calls.append(keyword)
        return _fake_discover(keyword, 10)

    monkeypatch.setattr("app.services.crawler.manmanbuy.discover_products", fake)
    client.get("/api/products/discover", params={"n": 8})
    r = client.get("/api/products/discover", params={"n": 3})
    assert len(calls) == 1  # 第二次命中缓存
    assert len(r.json()["items"]) == 3  # items[:n] 截取


def test_discover_refresh_bypasses_cache(client, monkeypatch):
    calls = []

    def fake(keyword, limit=20):
        calls.append(keyword)
        return _fake_discover(keyword, 10)

    monkeypatch.setattr("app.services.crawler.manmanbuy.discover_products", fake)
    client.get("/api/products/discover")
    client.get("/api/products/discover", params={"refresh": 1})
    assert len(calls) == 2


# ================= 链接收录 =================

def _fake_query_history_ok(url, timeout_ms=0):
    return {
        "title": "抓取到的商品", "image_url": "https://img.example.com/1.jpg",
        "history": [("2026-01-01", 90.0), ("2026-01-02", 95.0)],
        "price": 99.0, "platform": "jd",
    }


def test_import_invalid_url_400(client):
    r = client.post("/api/products/import", json={"url": "ftp://bad"})
    assert r.status_code == 400 and "链接不合法" in r.json()["detail"]


def test_import_existing_returns_early(client, db):
    p = make_product(db)
    make_listing(db, p, url="https://item.jd.com/exist.html")
    r = client.post("/api/products/import", json={"url": "https://item.jd.com/exist.html"})
    assert r.status_code == 200 and "已在库中" in r.json()["message"]


def test_import_success_crawl_data_used(client, db, monkeypatch):
    # title/price/platform 全部取爬虫数据；历史价格入库
    monkeypatch.setattr("app.services.crawler.manmanbuy.live_product", _fake_query_history_ok)
    r = client.post("/api/products/import", json={"url": "https://item.jd.com/new1.html", "category": "手机"})
    data = r.json()
    assert data["ok"] is True and "历史价格 2 天" in data["message"] and "历史查询" not in data["message"]
    detail = client.get(f"/api/products/{data['product_id']}").json()
    assert detail["name"] == "抓取到的商品"
    assert detail["listings"][0]["platform"] == "jd"
    assert detail["listings"][0]["current_price"] == 99.0


def test_import_body_fields_fallback(client, db, monkeypatch):
    # 爬虫返回空 title/price/platform -> 使用 body.title/body.price/默认平台；
    # price=0 -> current_price 为 None 的条件分支
    def fake(url, timeout_ms=0):
        return {"title": "", "image_url": "", "history": [], "price": None, "platform": ""}

    monkeypatch.setattr("app.services.crawler.manmanbuy.live_product", fake)
    r = client.post("/api/products/import", json={
        "url": "https://item.taobao.com/new2.html", "title": "自带标题", "price": 0,
    })
    data = r.json()
    assert "历史价格 0 天" in data["message"]
    detail = client.get(f"/api/products/{data['product_id']}").json()
    assert detail["name"] == "自带标题"
    assert detail["listings"][0]["platform"] == "taobao"
    # price=0 -> 走 `if price else None` 的 None 分支；
    # ORM 列默认值 0.0 对显式 None 生效，落库后读出为 0.0
    assert detail["listings"][0]["current_price"] == 0.0


def test_import_crawl_fail_no_title_502(client, db, monkeypatch):
    def fake(url, timeout_ms=0):
        raise RuntimeError("慢慢买超时")

    monkeypatch.setattr("app.services.crawler.manmanbuy.live_product", fake)
    r = client.post("/api/products/import", json={"url": "https://item.jd.com/new3.html"})
    assert r.status_code == 502 and "未能获取商品标题" in r.json()["detail"]


def test_import_crawl_fail_empty_title_502(client, db, monkeypatch):
    # 爬虫成功但标题为空 -> 同样 502（crawl_err 为空的报错分支）
    monkeypatch.setattr("app.services.crawler.manmanbuy.live_product",
                        lambda url, timeout_ms=0: {"title": "", "image_url": "", "history": [], "price": 1.0, "platform": "jd"})
    r = client.post("/api/products/import", json={"url": "https://item.jd.com/new4.html"})
    assert r.status_code == 502


def test_import_crawl_fail_with_body_title(client, db, monkeypatch):
    # 爬虫失败但 body.title 存在 -> 收录成功，message 带历史查询错误后缀
    def fake(url, timeout_ms=0):
        raise RuntimeError("解析失败")

    monkeypatch.setattr("app.services.crawler.manmanbuy.live_product", fake)
    r = client.post("/api/products/import", json={
        "url": "https://item.jd.com/new5.html", "title": "手动标题", "price": 66.0,
    })
    data = r.json()
    assert data["ok"] is True and "（历史查询：" in data["message"]
    detail = client.get(f"/api/products/{data['product_id']}").json()
    assert detail["listings"][0]["current_price"] == 66.0


def test_import_removes_from_discover_cache(client, db, monkeypatch):
    products_mod._discover_cache["items"] = [{"url": "https://item.jd.com/new6.html", "title": "x"}]
    monkeypatch.setattr("app.services.crawler.manmanbuy.live_product", _fake_query_history_ok)
    r = client.post("/api/products/import", json={"url": "https://item.jd.com/new6.html"})
    assert r.status_code == 200
    assert products_mod._discover_cache["items"] == []


def test_import_with_history_skips_crawl(client, db, monkeypatch):
    # 实时详情已拿到历史价 -> 直接落库，不再触发爬虫
    def boom(url, timeout_ms=0):
        raise AssertionError("不应触发爬虫")

    monkeypatch.setattr("app.services.crawler.manmanbuy.live_product", boom)
    r = client.post("/api/products/import", json={
        "url": "https://item.jd.com/new7.html", "title": "实时商品", "price": 88.0,
        "image": "https://img.example.com/7.jpg", "platform": "jd",
        "history": [{"date": "2026-01-01", "price": 80.0}, {"date": "2026-01-02", "price": 88.0}],
    })
    data = r.json()
    assert data["ok"] is True and "历史价格 2 天" in data["message"]
    detail = client.get(f"/api/products/{data['product_id']}").json()
    assert detail["name"] == "实时商品"
    assert detail["listings"][0]["platform"] == "jd"


# ================= 商品详情 =================

def test_detail_ok(client, db):
    p1, _, _ = _seed_products(db)
    r = client.get(f"/api/products/{p1.id}")
    assert r.status_code == 200
    detail = r.json()
    assert detail["min_price"] == 1899.0
    jd = next(l for l in detail["listings"] if l["platform"] == "jd")
    assert [s["price"] for s in jd["recent_snapshots"]] == [1999.0, 1950.0]  # 时间升序


def test_detail_404(client, db):
    r = client.get("/api/products/99999")
    assert r.status_code == 404 and "商品不存在" in r.json()["detail"]


# ================= 实时价格查询 =================

def test_realtime_invalid_url_400(client):
    r = client.post("/api/products/realtime", json={"url": "javascript:alert(1)"})
    assert r.status_code == 400 and "合法" in r.json()["detail"]


def test_realtime_crawl_exception_502(client, monkeypatch):
    monkeypatch.setattr(products_mod, "realtime_crawl", lambda url: (_ for _ in ()).throw(RuntimeError("页面打不开")))
    r = client.post("/api/products/realtime", json={"url": "https://item.jd.com/x.html"})
    assert r.status_code == 502 and "采集失败" in r.json()["detail"]


def test_realtime_crawl_none_502(client, monkeypatch):
    monkeypatch.setattr(products_mod, "realtime_crawl", lambda url: None)
    r = client.post("/api/products/realtime", json={"url": "https://item.jd.com/x.html"})
    assert r.status_code == 502 and "未能从页面解析出价格" in r.json()["detail"]


def test_realtime_success_full_fields(client, monkeypatch):
    monkeypatch.setattr(products_mod, "realtime_crawl", lambda url: {
        "platform": "jd", "title": "实时商品", "price": 123.4, "image_url": "https://img/1.jpg",
    })
    r = client.post("/api/products/realtime", json={"url": "https://item.jd.com/x.html"})
    data = r.json()
    assert data["price"] == 123.4 and data["title"] == "实时商品" and data["captured_at"]


def test_realtime_success_missing_optional_fields(client, monkeypatch):
    # title/image_url 缺省 -> .get 默认空串分支
    monkeypatch.setattr(products_mod, "realtime_crawl", lambda url: {"platform": "web", "price": 9.9})
    r = client.post("/api/products/realtime", json={"url": "https://other.example.com/x"})
    data = r.json()
    assert data["title"] == "" and data["image_url"] == ""


def test_realtime_url_schema_422(client):
    # RealtimeCrawlIn 长度约束
    r = client.post("/api/products/realtime", json={"url": "short"})
    assert r.status_code == 422


# ================= 爬虫核心：平台识别与采集调度（crawler/core.py） =================

def test_detect_platform_variants():
    from app.services.crawler import core as crawler_core

    cases = {
        "https://item.jd.com/1.html": "jd",
        "https://item.m.jd.com/1": "jd",
        "https://detail.tmall.com/a": "taobao",   # 天猫归入淘宝系
        "https://item.taobao.com/a": "taobao",
        "https://www.pinduoduo.com/a": "pdd",
        "https://www.manmanbuy.com/a": "manmanbuy",
        "https://product.dangdang.com/a": "dangdang",
        "https://product.suning.com/a": "suning",
        "https://www.vip.com/a": "vip",
        "https://www.amazon.cn/a": "amazon",
        "https://www.example.com/a": "web",
    }
    for url, expect in cases.items():
        assert crawler_core.detect_platform(url) == expect


def test_fetch_price_generic_first(monkeypatch):
    from app.services.crawler import core as crawler_core

    monkeypatch.setattr("app.services.crawler.generic.fetch",
                        lambda url: {"price": 12.5, "title": "T"})
    out = crawler_core.fetch_price("https://www.example.com/a")
    assert out["price"] == 12.5
    # setdefault 补全 platform/history 可选字段
    assert out["platform"] == "web" and out["history"] == []


def test_fetch_price_falls_through_to_manmanbuy(monkeypatch):
    from app.services.crawler import core as crawler_core

    monkeypatch.setattr("app.services.crawler.jd.fetch",
                        lambda url: (_ for _ in ()).throw(RuntimeError("京东失败")))
    monkeypatch.setattr("app.services.crawler.manmanbuy.fetch", lambda url: {"price": 8.8})
    out = crawler_core.fetch_price("https://item.jd.com/1.html")
    assert out["price"] == 8.8  # jd 失败后顺延 manmanbuy


def test_fetch_price_all_failed_raises(monkeypatch):
    from app.services.crawler import core as crawler_core

    def boom(name):
        def _f(url):
            raise RuntimeError(name)
        return _f

    monkeypatch.setattr("app.services.crawler.generic.fetch", boom("通用失败"))
    monkeypatch.setattr("app.services.crawler.manmanbuy.fetch", boom("慢慢买失败"))
    with pytest.raises(RuntimeError) as e:
        crawler_core.fetch_price("https://www.example.com/a")
    assert "通用失败" in str(e.value) and "慢慢买失败" in str(e.value)


def test_fetch_price_empty_result_counts_as_error(monkeypatch):
    from app.services.crawler import core as crawler_core

    monkeypatch.setattr("app.services.crawler.generic.fetch", lambda url: {})
    monkeypatch.setattr("app.services.crawler.manmanbuy.fetch",
                        lambda url: (_ for _ in ()).throw(RuntimeError("x")))
    with pytest.raises(RuntimeError):
        crawler_core.fetch_price("https://www.example.com/a")


def test_realtime_crawl_dispatch(monkeypatch):
    from app.services.crawler import core as crawler_core

    monkeypatch.setattr("app.services.crawler.generic.fetch", lambda url: {"price": 5.5})
    out = crawler_core.realtime_crawl("https://www.example.com/b")
    assert out["price"] == 5.5
