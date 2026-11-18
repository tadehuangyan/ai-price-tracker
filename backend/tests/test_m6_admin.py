# -*- coding: utf-8 -*-
"""M6 系统管理 测试（admin.py + services/crawler/core.run_crawl_task）

覆盖目标：数据源管理、采集任务调度与监控、统计数据、系统日志、系统配置、
用户管理、敏感词管理的语句与条件覆盖。采集执行在 fetch_price 边界 mock。
"""
from datetime import datetime, timedelta

import pytest

from app.models import (
    CrawlTask,
    DataSource,
    SensitiveWord,
    SystemConfig,
    SystemLog,
)
from app.services.crawler import core as crawler_core

from conftest import auth_headers, make_listing, make_product, make_user


@pytest.fixture()
def admin(db):
    """夹具：创建一个管理员用户"""
    return make_user(db, username="admin1", email="admin1@qq.com", role="admin")


@pytest.fixture()
def headers(admin):
    """夹具：返回管理员的鉴权请求头"""
    return auth_headers(admin)


# ================= 权限 =================

def test_admin_api_requires_admin(client, db):
    """【异常流】普通用户访问全部管理接口均返回 403"""
    u = make_user(db, username="nobody", email="nobody@qq.com")
    for path in ("/api/admin/datasources", "/api/admin/tasks", "/api/admin/stats",
                 "/api/admin/logs", "/api/admin/config", "/api/admin/users",
                 "/api/admin/sensitive-words"):
        assert client.get(path, headers=auth_headers(u)).status_code == 403


# ================= 数据源管理 =================

def test_list_datasources(client, db, headers):
    """【正常流】数据源列表返回全部记录，覆盖 updated_at 有值/为空分支"""
    db.add(DataSource(platform="jd", name="京东", enabled=True, config="{}"))
    d2 = DataSource(platform="taobao", name="淘宝", enabled=False, config="{}")
    db.add(d2)
    db.commit()
    d2.updated_at = None  # 显式置空（插入时列默认值会填充）
    db.commit()
    r = client.get("/api/admin/datasources", headers=headers)
    items = r.json()
    assert len(items) == 2
    by_p = {i["platform"]: i for i in items}
    assert by_p["jd"]["updated_at"] is not None
    assert by_p["taobao"]["updated_at"] is None  # updated_at 为空的条件分支


def test_save_datasource_create_with_name_and_config(client, db, headers):
    """【正常流】新建数据源保存名称/采集周期/配置并记录操作日志"""
    r = client.post("/api/admin/datasources", json={
        "platform": "suning", "name": "苏宁", "enabled": True,
        "crawl_interval_minutes": 720, "config": '{"k": 1}',
    }, headers=headers)
    assert r.status_code == 200
    d = db.query(DataSource).filter(DataSource.platform == "suning").first()
    assert d.name == "苏宁" and d.crawl_interval_minutes == 720 and d.config == '{"k": 1}'
    assert db.query(SystemLog).filter(SystemLog.module == "datasource").count() == 1


def test_save_datasource_update_name_fallbacks(client, db, headers):
    """【边界】保存数据源时名称缺省链与配置缺省回退生效"""
    # name 缺省链：body.name -> d.name -> platform；config 缺省 -> "{}"
    db.add(DataSource(platform="jd", name="京东", enabled=True, config="{}"))
    db.commit()
    client.post("/api/admin/datasources", json={"platform": "jd"}, headers=headers)
    d = db.query(DataSource).filter(DataSource.platform == "jd").first()
    assert d.name == "京东" and d.config == "{}"  # 保留原名
    client.post("/api/admin/datasources", json={"platform": "newp"}, headers=headers)
    d2 = db.query(DataSource).filter(DataSource.platform == "newp").first()
    assert d2.name == "newp" and d2.config == "{}"  # 回退 platform


# ================= 采集任务 =================

def _tasks(db):
    """辅助函数：构造一条成功、一条失败的采集任务"""
    t1 = CrawlTask(platform="jd", target="https://j/1", listing_id=None,
                   status="success", last_run_at=datetime.now(), success_count=2)
    t2 = CrawlTask(platform="taobao", target="https://t/1", listing_id=None,
                   status="failed", last_run_at=None, fail_count=1)
    db.add_all([t1, t2])
    db.commit()
    return t1, t2


def test_list_tasks_no_filter_and_filter(client, db, headers):
    """【正常流】任务列表支持无过滤与按状态过滤"""
    _tasks(db)
    r_all = client.get("/api/admin/tasks", headers=headers)
    assert r_all.json()["total"] == 2
    # last_run_at 为空 / 非空两个条件分支
    items = {i["platform"]: i for i in r_all.json()["items"]}
    assert items["jd"]["last_run_at"] is not None
    assert items["taobao"]["last_run_at"] is None
    r_f = client.get("/api/admin/tasks", params={"status": "failed"}, headers=headers)
    assert r_f.json()["total"] == 1


def test_list_tasks_pagination(client, db, headers):
    """【正常流】任务列表分页参数生效"""
    _tasks(db)
    r = client.get("/api/admin/tasks", params={"page": 2, "page_size": 1}, headers=headers)
    assert r.json()["total"] == 2 and len(r.json()["items"]) == 1


def test_run_task_404(client, db, headers):
    """【异常流】运行不存在的采集任务返回 404"""
    r = client.post("/api/admin/tasks/99999/run", headers=headers)
    assert r.status_code == 404


def test_run_task_success_updates_listing(client, db, headers, monkeypatch):
    """【正常流】任务执行成功后回写报价/标题并记录成功日志"""
    p = make_product(db)
    l = make_listing(db, p, current_price=100.0)
    t = CrawlTask(platform="jd", target="https://j/1", listing_id=l.id, status="pending")
    db.add(t)
    db.commit()
    monkeypatch.setattr(crawler_core, "fetch_price",
                        lambda url: {"price": 88.0, "title": "新标题", "history": []})
    r = client.post(f"/api/admin/tasks/{t.id}/run", headers=headers)
    assert r.json() == {"ok": True, "error": ""}
    assert t.status == "success" and t.success_count == 1 and t.last_error == ""
    assert l.current_price == 88.0 and l.title == "新标题" and l.last_crawled_at is not None
    assert db.query(SystemLog).filter(SystemLog.module == "task", SystemLog.level == "INFO").count() == 1


def test_run_task_success_without_listing(client, db, headers, monkeypatch):
    """【边界】任务未关联报价链接时不回写报价"""
    # listing_id 为空 -> 不回写报价的条件分支
    t = CrawlTask(platform="web", target="https://x/1", listing_id=None, status="pending")
    db.add(t)
    db.commit()
    monkeypatch.setattr(crawler_core, "fetch_price", lambda url: {"price": 1.0})
    r = client.post(f"/api/admin/tasks/{t.id}/run", headers=headers)
    assert r.json()["ok"] is True and t.status == "success"


def test_run_task_no_price_fails(client, db, headers, monkeypatch):
    """【异常流】采集未解析到价格时任务标记失败并记 ERROR 日志"""
    t = CrawlTask(platform="jd", target="https://j/1", listing_id=None, status="pending")
    db.add(t)
    db.commit()
    monkeypatch.setattr(crawler_core, "fetch_price", lambda url: {"price": None})
    r = client.post(f"/api/admin/tasks/{t.id}/run", headers=headers)
    data = r.json()
    assert data["ok"] is False and data["error"] == "未解析到价格"
    assert t.status == "failed" and t.fail_count == 1
    assert db.query(SystemLog).filter(SystemLog.level == "ERROR").count() == 1  # 日志级别 ERROR 分支


def test_run_task_exception_fails(client, db, headers, monkeypatch):
    """【异常流】采集抛异常时任务标记失败并记录错误信息"""
    t = CrawlTask(platform="jd", target="https://j/1", listing_id=None, status="pending")
    db.add(t)
    db.commit()

    def boom(url):
        raise RuntimeError("页面打不开")

    monkeypatch.setattr(crawler_core, "fetch_price", boom)
    r = client.post(f"/api/admin/tasks/{t.id}/run", headers=headers)
    assert r.json()["ok"] is False and "页面打不开" in r.json()["error"]
    assert t.status == "failed" and "页面打不开" in t.last_error


def test_pause_and_resume_task(client, db, headers):
    """【正常流】任务暂停与恢复状态切换正确"""
    t1, t2 = _tasks(db)
    assert client.post(f"/api/admin/tasks/{t1.id}/pause", headers=headers).json()["ok"] is True
    assert db.query(CrawlTask).get(t1.id).status == "paused"
    assert client.post(f"/api/admin/tasks/{t2.id}/resume", headers=headers).json()["ok"] is True
    assert db.query(CrawlTask).get(t2.id).status == "pending"


def test_pause_and_resume_404(client, db, headers):
    """【异常流】暂停/恢复不存在的任务返回 404"""
    assert client.post("/api/admin/tasks/99999/pause", headers=headers).status_code == 404
    assert client.post("/api/admin/tasks/99999/resume", headers=headers).status_code == 404


# ================= 统计与日志 =================

def test_stats_with_tasks(client, db, headers):
    """【正常流】统计数据正确汇总任务成败与各业务计数"""
    _tasks(db)  # 1 success + 1 failed，均在 1 天内运行（failed 的 last_run_at 为 None 不计近期）
    data = client.get("/api/admin/stats", headers=headers).json()
    assert data["task_total"] == 2 and data["task_success"] == 1 and data["task_failed"] == 1
    assert data["success_rate"] == 100.0  # 近期(1条)全部成功
    for key in ("product_count", "listing_count", "snapshot_count", "user_count",
                "tracking_count", "alert_count"):
        assert isinstance(data[key], int)


def test_stats_no_recent_tasks_success_rate_none(client, db, headers):
    """【边界】近期无任务时成功率返回 null"""
    # recent_total 为 0 -> success_rate None 的条件分支
    db.add(CrawlTask(platform="jd", target="x", status="success",
                     last_run_at=datetime.now() - timedelta(days=30)))
    db.commit()
    data = client.get("/api/admin/stats", headers=headers).json()
    assert data["success_rate"] is None


def test_logs_filters(client, db, headers):
    """【正常流】日志列表支持按级别/模块过滤，覆盖 created_at 为空分支"""
    m3 = SystemLog(level="INFO", module="alert", message="m3")
    db.add_all([
        SystemLog(level="INFO", module="task", message="m1"),
        SystemLog(level="ERROR", module="crawl", message="m2"),
        m3,
    ])
    db.commit()
    m3.created_at = None
    db.commit()
    assert client.get("/api/admin/logs", headers=headers).json()["total"] == 3
    assert client.get("/api/admin/logs", params={"level": "ERROR"}, headers=headers).json()["total"] == 1
    assert client.get("/api/admin/logs", params={"module": "task"}, headers=headers).json()["total"] == 1
    r = client.get("/api/admin/logs", headers=headers)
    items = {i["message"]: i for i in r.json()["items"]}
    assert items["m3"]["created_at"] is None  # created_at 为空的条件分支


def test_logs_pagination_params_422(client, db, headers):
    """【异常流】非法分页参数被 schema 拦截返回 422"""
    assert client.get("/api/admin/logs", params={"page": 0}, headers=headers).status_code == 422
    assert client.get("/api/admin/logs", params={"page_size": 101}, headers=headers).status_code == 422


# ================= 系统配置 =================

def test_get_config(client, db, headers):
    """【正常流】系统配置列表返回键值，覆盖 updated_at 为空分支"""
    db.add(SystemConfig(key="k1", value="v1", description="d1"))
    c2 = SystemConfig(key="k2", value="v2", description="d2")
    db.add(c2)
    db.commit()
    c2.updated_at = None
    db.commit()
    items = {i["key"]: i for i in client.get("/api/admin/config", headers=headers).json()}
    assert items["k1"]["updated_at"] is not None
    assert items["k2"]["updated_at"] is None


def test_set_config_update_and_create(client, db, headers):
    """【正常流】配置项存在则更新、不存在则新建，均记操作日志"""
    db.add(SystemConfig(key="k1", value="old", description="d1"))
    db.commit()
    assert client.put("/api/admin/config", json={"key": "k1", "value": "new"},
                      headers=headers).json()["ok"] is True
    assert db.query(SystemConfig).get("k1").value == "new"
    assert client.put("/api/admin/config", json={"key": "k9", "value": "v9"},
                      headers=headers).json()["ok"] is True
    assert db.query(SystemConfig).get("k9").value == "v9"  # 不存在 -> 新建分支
    assert db.query(SystemLog).filter(SystemLog.module == "config").count() == 2


# ================= 用户管理 =================

def test_list_users_filters(client, db, headers):
    """【正常流】用户列表支持关键词（用户名/邮箱 OR）过滤与分页"""
    make_user(db, username="findme", email="find@qq.com")
    make_user(db, username="other1", email="findtarget@qq.com")
    make_user(db, username="unrelated", email="u@qq.com")
    assert client.get("/api/admin/users", headers=headers).json()["total"] == 4  # 含 admin
    # OR 条件：命中用户名 / 命中邮箱 / 无过滤
    assert client.get("/api/admin/users", params={"keyword": "findme"},
                      headers=headers).json()["total"] == 1
    assert client.get("/api/admin/users", params={"keyword": "findtarget"},
                      headers=headers).json()["total"] == 1
    r = client.get("/api/admin/users", params={"page": 2, "page_size": 2}, headers=headers)
    assert len(r.json()["items"]) == 2


def test_set_user_status(client, db, headers, admin):
    """【正常流】管理员修改用户状态并记录操作日志"""
    u = make_user(db, username="target1", email="t1@qq.com")
    r = client.post(f"/api/admin/users/{u.id}/status", params={"status": "disabled"},
                    headers=headers)
    assert r.json()["ok"] is True
    assert db.query(type(u)).get(u.id).status == "disabled"
    assert db.query(SystemLog).filter(SystemLog.module == "user").count() == 1


def test_set_user_status_self_forbidden(client, db, headers, admin):
    """【异常流】管理员不能禁用自己的账号"""
    # 不能禁用自己的条件分支
    r = client.post(f"/api/admin/users/{admin.id}/status", params={"status": "disabled"},
                    headers=headers)
    assert r.status_code == 400 and "不能禁用自己" in r.json()["detail"]


def test_set_user_status_404_and_bad_pattern(client, db, headers):
    """【异常流】用户不存在返回 404，非法状态值返回 422"""
    assert client.post("/api/admin/users/99999/status", params={"status": "active"},
                       headers=headers).status_code == 404
    assert client.post("/api/admin/users/1/status", params={"status": "banned"},
                       headers=headers).status_code == 422


# ================= 敏感词管理 =================

def test_list_sensitive_words_filter(client, db, headers):
    """【正常流】敏感词列表支持关键词过滤"""
    db.add_all([SensitiveWord(word="赌博", category="违法"),
                SensitiveWord(word="诈骗", category="违法")])
    db.commit()
    assert client.get("/api/admin/sensitive-words", headers=headers).json()["total"] == 2
    r = client.get("/api/admin/sensitive-words", params={"keyword": "赌"}, headers=headers)
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["word"] == "赌博"
    assert r.json()["items"][0]["created_at"] is not None


def test_add_sensitive_word(client, db, headers):
    """【正常流】新增敏感词成功，分类缺省为通用"""
    r = client.post("/api/admin/sensitive-words", json={"word": "违禁品"},
                    headers=headers)
    assert r.json()["ok"] is True
    w = db.query(SensitiveWord).filter(SensitiveWord.word == "违禁品").first()
    assert w.category == "通用"  # category 缺省分支
    assert db.query(SystemLog).filter(SystemLog.module == "moderation").count() == 1


def test_add_sensitive_word_blank_400(client, db, headers):
    """【异常流】空白敏感词被拒绝"""
    r = client.post("/api/admin/sensitive-words", json={"word": "   "}, headers=headers)
    assert r.status_code == 400 and "不能为空" in r.json()["detail"]


def test_add_sensitive_word_duplicate_400(client, db, headers):
    """【异常流】重复敏感词被拒绝"""
    db.add(SensitiveWord(word="赌博"))
    db.commit()
    r = client.post("/api/admin/sensitive-words", json={"word": "赌博", "category": "违法"},
                    headers=headers)
    assert r.status_code == 400 and "已存在" in r.json()["detail"]


def test_add_sensitive_words_batch(client, db, headers):
    """【正常流】批量新增敏感词，空行/超长/重复被跳过并统计"""
    db.add(SensitiveWord(word="已有词"))
    db.commit()
    words = "新词1\n新词2\n\n   \n已有词\n" + "x" * 65
    r = client.post("/api/admin/sensitive-words/batch",
                    json={"words": words, "category": "批量"}, headers=headers)
    data = r.json()
    # 新增 2 个；空行/超长/重复各跳过
    assert data["added"] == 2 and data["skipped"] == 4
    assert db.query(SensitiveWord).count() == 3
    assert db.query(SystemLog).filter(SystemLog.module == "moderation").count() == 1


def test_add_sensitive_words_batch_category_default(client, db, headers):
    """【边界】批量新增未指定分类时回退为通用"""
    r = client.post("/api/admin/sensitive-words/batch", json={"words": "默认类词"}, headers=headers)
    assert r.json()["added"] == 1
    assert db.query(SensitiveWord).filter(SensitiveWord.word == "默认类词").first().category == "通用"


def test_delete_sensitive_word(client, db, headers):
    """【正常流】删除敏感词成功并记录操作日志"""
    w = SensitiveWord(word="待删除")
    db.add(w)
    db.commit()
    assert client.delete(f"/api/admin/sensitive-words/{w.id}", headers=headers).json()["ok"] is True
    assert db.query(SensitiveWord).count() == 0
    assert db.query(SystemLog).filter(SystemLog.module == "moderation").count() == 1


def test_delete_sensitive_word_404(client, db, headers):
    """【异常流】删除不存在的敏感词返回 404"""
    assert client.delete("/api/admin/sensitive-words/99999", headers=headers).status_code == 404


# ================= 调度器（scheduler.py） =================

def test_scheduler_job_collect_branches(monkeypatch, db):
    """到点采集：成功/无价失败/异常失败/未到点跳过/标题回退 全部分支"""
    from app import scheduler as sched
    from conftest import TestingSession

    p = make_product(db)
    l1 = make_listing(db, p, platform="jd", url="https://j/1", current_price=100.0)   # 成功（带标题）
    l2 = make_listing(db, p, platform="taobao", url="https://x/2", current_price=100.0)   # price 空 -> 失败
    l3 = make_listing(db, p, platform="pdd", url="https://x/3", current_price=100.0)   # 异常 -> 失败 + 日志
    l4 = make_listing(db, p, platform="web", url="https://x/4", current_price=100.0,
                      last_crawled_at=datetime.now())                  # 未到点 -> 过滤跳过
    l5 = make_listing(db, p, platform="dangdang", url="https://x/5", current_price=100.0)   # data 空 -> 失败
    l6 = make_listing(db, p, platform="suning", url="https://x/6", current_price=100.0,
                      title="原标题")                                   # 成功但无标题 -> 保留原标题

    def fake_fetch(url):
        if url.endswith("/2"):
            return {"price": None}
        if url.endswith("/3"):
            raise RuntimeError("采集失败")
        if url.endswith("/5"):
            return {}
        return {"price": 66.0 if url.endswith("/1") else 7.0,
                "title": "采集标题" if url.endswith("/1") else ""}

    monkeypatch.setattr(sched, "SessionLocal", TestingSession)
    monkeypatch.setattr("app.services.crawler.fetch_price", fake_fetch)

    sched.job_collect()
    db.expire_all()
    assert db.query(CrawlTask).count() == 5  # l4 未生成任务
    by_url = {t.target: t for t in db.query(CrawlTask).all()}
    assert by_url["https://j/1"].status == "success" and by_url["https://j/1"].success_count == 1
    assert by_url["https://x/2"].status == "failed" and by_url["https://x/2"].last_error == "未解析到价格"
    assert by_url["https://x/3"].status == "failed" and "采集失败" in by_url["https://x/3"].last_error
    assert by_url["https://x/5"].status == "failed" and by_url["https://x/5"].last_error == "未解析到价格"
    assert by_url["https://x/6"].status == "success"
    assert all(t.last_run_at is not None for t in by_url.values())
    assert db.get(type(l1), l1.id).current_price == 66.0   # 成功回写报价
    assert db.get(type(l6), l6.id).title == "原标题"        # 无标题 -> 保留原值
    assert db.get(type(l4), l4.id).current_price == 100.0  # 未到点的报价不动
    assert db.query(SystemLog).filter(SystemLog.level == "ERROR").count() == 1  # 仅 l3 记异常日志


def test_scheduler_config_lookup(db):
    """覆盖调度器配置读取：无配置取默认 / 有值取值 / 空值取默认"""
    # _config：无配置取默认值 / 有值取值 / 空值取默认值
    from app import scheduler as sched

    assert sched._config(db, "crawl_interval_minutes", "1440") == "1440"
    db.add(SystemConfig(key="crawl_interval_minutes", value="30"))
    db.commit()
    assert sched._config(db, "crawl_interval_minutes", "1440") == "30"
    row = db.query(SystemConfig).get("crawl_interval_minutes")
    row.value = ""
    db.commit()
    assert sched._config(db, "crawl_interval_minutes", "1440") == "1440"


def test_scheduler_job_collect_bad_config_survives(monkeypatch, db):
    """【异常流】配置值非法时采集任务被外层异常兜底，不向外抛出"""
    # 配置值非法 -> 任务级外层异常兜底（不抛出）
    from app import scheduler as sched
    from conftest import TestingSession

    db.add(SystemConfig(key="crawl_interval_minutes", value="abc"))
    db.commit()
    monkeypatch.setattr(sched, "SessionLocal", TestingSession)
    monkeypatch.setattr("app.services.crawler.fetch_price", lambda url: {"price": 1.0})
    sched.job_collect()  # 不应抛出


def test_job_alerts_logs_generated(monkeypatch, db):
    """【正常流】提醒任务生成后记日志，n=0 时不记日志"""
    from app import scheduler as sched
    from conftest import TestingSession

    monkeypatch.setattr(sched, "SessionLocal", TestingSession)
    monkeypatch.setattr(sched, "check_price_alerts", lambda s: 3)  # 模块级导入，需替换调度器命名空间
    sched.job_alerts()
    log = db.query(SystemLog).filter(SystemLog.module == "alert").first()
    assert "产生 3 条降价提醒" in log.message
    # n=0 -> 不记日志的分支
    monkeypatch.setattr(sched, "check_price_alerts", lambda s: 0)
    sched.job_alerts()
    assert db.query(SystemLog).filter(SystemLog.module == "alert").count() == 1


def test_scheduler_start_and_shutdown(monkeypatch):
    """【正常流】调度器启动注册任务，重复启动不叠加任务"""
    from app import scheduler as sched

    monkeypatch.setattr(sched, "job_collect", lambda: None)
    monkeypatch.setattr(sched, "job_alerts", lambda: None)
    sched.start_scheduler()
    assert sched.scheduler.running
    assert len(sched.scheduler.get_jobs()) == 3  # 启动补偿任务 + 两个周期任务
    sched.start_scheduler()  # 已在运行 -> 不重复启动分支
    assert len(sched.scheduler.get_jobs()) == 3
    sched.scheduler.shutdown(wait=False)


def test_job_alerts_exception_survives(monkeypatch, db):
    """【异常流】提醒任务抛异常被兜底，不向外抛出"""
    # check_price_alerts 异常 -> 任务级兜底（不抛出）
    from app import scheduler as sched
    from conftest import TestingSession

    monkeypatch.setattr(sched, "SessionLocal", TestingSession)

    def boom(s):
        raise RuntimeError("alerts 失败")

    monkeypatch.setattr(sched, "check_price_alerts", boom)
    sched.job_alerts()  # 不应抛出
