# -*- coding: utf-8 -*-
"""M8 知识库（RAG）与识图（多模态闭环）测试

覆盖目标：knowledge 关键词检索（tags/标题/正文命中、阈值与截断）、chat 链路知识注入
与 sources 引用来源、query_knowledge 工具、管理端知识库 CRUD、vision 识图解析与
image_search 端点（本地候选 + 联网降级）。大模型与爬虫在接口边界 mock。
"""
import json as _json

from app.models import KnowledgeArticle
from app.services import agent_tools, ai_advisor, knowledge, vision

from conftest import auth_headers, make_listing, make_product, make_user


def _add_article(db, title="双11 大促规律", tags="双11,大促,便宜",
                 content="双11 两波现货期，跨店满减每 300 减 50，先查历史价格。", category="大促规律"):
    """辅助函数：向知识库插入一篇测试文章"""
    a = KnowledgeArticle(title=title, category=category, tags=tags, content=content)
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def _client_user(db, role="user"):
    """辅助函数：创建知识库测试用户（可指定角色）"""
    return make_user(db, username="kb_user", email="kb@qq.com", role=role)


def _parse_sse(text):
    """辅助函数：解析 SSE 文本，提取 data: 行为 JSON 事件列表"""
    events = []
    for part in text.split("\n\n"):
        part = part.strip()
        if part.startswith("data:"):
            events.append(_json.loads(part[5:].strip()))
    return events


# ================= knowledge.retrieve 检索 =================

def test_retrieve_tag_hit(db):
    """【正常流】检索命中文章标签，返回上下文与引用来源"""
    a = _add_article(db)
    ctxs, sources = knowledge.retrieve(db, "双11 什么时候买最便宜")
    assert len(ctxs) == 1 and ctxs[0].startswith(f"【知识库 K{a.id}｜双11 大促规律】")
    assert sources[0]["title"] == "双11 大促规律"


def test_retrieve_title_and_content_tokens(db):
    """【正常流】标题 2-gram 与正文命中共同参与检索排序"""
    # 标题 2-gram 命中（+2）与正文命中（+1）均参与排序
    a = _add_article(db, title="空调选购避坑", tags="家电", content="匹数与能效比是空调选购核心")
    _ctxs, sources = knowledge.retrieve(db, "空调怎么选")
    assert sources and sources[0]["id"] == a.id


def test_retrieve_threshold_and_limit(db):
    """【边界】低于得分阈值不返回，多条命中按得分取 top-N"""
    # 无任何命中（低于阈值）不返回；命中多条按得分取 top-N
    _add_article(db, title="无关条目", tags="zzz", content="zzz")
    assert knowledge.retrieve(db, "蓝牙耳机推荐")[1] == []
    for i in range(5):
        _add_article(db, title=f"双11 攻略{i}", tags="双11", content="双11 便宜")
    _ctxs, sources = knowledge.retrieve(db, "双11", limit=3)
    assert len(sources) == 3


def test_retrieve_empty_query(db):
    """【边界】空查询词不返回任何结果"""
    assert knowledge.retrieve(db, "") == ([], [])


def test_retrieve_disabled_article_excluded(db):
    """【边界】已停用的文章不参与检索"""
    a = _add_article(db)
    a.enabled = False
    db.commit()
    assert knowledge.retrieve(db, "双11 便宜")[1] == []


# ================= chat 链路集成 =================

def test_chat_reply_injects_knowledge_and_sources(db, monkeypatch):
    """【正常流】聊天链路注入知识库上下文并返回引用来源"""
    _add_article(db)
    calls = []
    monkeypatch.setattr(ai_advisor, "llm_chat",
                        lambda messages, **k: calls.append(messages) or "建议等双11【来源：K1】")
    out = ai_advisor.chat_reply(db, "双11 什么时候最便宜", [])
    system = calls[0][0]["content"]
    assert "【知识库 K" in system and "知识库检索结果" in system
    assert out["sources"] and out["sources"][0]["title"] == "双11 大促规律"


def test_knowledge_not_in_fact_check_whitelist(db, monkeypatch):
    """【边界】知识库数字不进事实核对白名单，编造价格仍被标注"""
    # 知识库数字不进入事实核对白名单：编造的价格仍会被标注
    _add_article(db, content="该品类历史低价 3000 元")
    monkeypatch.setattr(ai_advisor, "llm_chat", lambda *a, **k: "现在只要 3000 元")
    out = ai_advisor.chat_reply(db, "双11 这台值得买吗", [])
    assert out["sources"]  # 知识库已命中并注入
    assert "未经系统数据验证" in out["reply"]  # 但 3000 不在商品数据白名单


def test_chat_stream_sources_event_first(client, db, monkeypatch):
    """【正常流】流式聊天先推送 sources 事件列出引用来源"""
    _add_article(db)
    monkeypatch.setattr(ai_advisor, "llm_chat_stream", lambda *a, **k: iter(["回答"])
    )
    u = _client_user(db)
    r = client.post("/api/advisor/chat/stream", json={"message": "双11 便宜吗"}, headers=auth_headers(u))
    events = _parse_sse(r.text)
    assert events[0]["type"] == "sources" and events[0]["items"][0]["title"] == "双11 大促规律"


# ================= query_knowledge 工具 =================

def test_tool_query_knowledge(db):
    """【正常流】query_knowledge 工具返回命中条目，缺参时提示必填字段"""
    _add_article(db)
    data = _json.loads(agent_tools.dispatch(db, None, "query_knowledge",
                                            _json.dumps({"question": "双11 怎么买"})))
    assert data["items"] and data["items"][0]["title"] == "双11 大促规律"
    assert "question" in agent_tools.dispatch(db, None, "query_knowledge", "{}")


# ================= 管理端知识库 CRUD =================

def test_admin_knowledge_crud(client, db):
    """【正常流】管理端知识库增删改查全链路可用"""
    u = _client_user(db, role="admin")
    h = auth_headers(u)
    body = {"title": "测试知识", "category": "测试", "tags": "测试,知识",
            "content": "测试内容", "enabled": True}
    assert client.post("/api/admin/knowledge", json=body, headers=h).json()["ok"] is True
    data = client.get("/api/admin/knowledge", headers=h).json()
    assert data["total"] == 1 and data["items"][0]["title"] == "测试知识"
    aid = data["items"][0]["id"]
    body["content"] = "更新后内容"
    assert client.put(f"/api/admin/knowledge/{aid}", json=body, headers=h).json()["ok"] is True
    assert client.get("/api/admin/knowledge?keyword=更新后", headers=h).json()["total"] == 1
    assert client.delete(f"/api/admin/knowledge/{aid}", headers=h).json()["ok"] is True
    assert client.get("/api/admin/knowledge", headers=h).json()["total"] == 0


def test_admin_knowledge_requires_admin(client, db):
    """【异常流】普通用户与未登录用户访问知识库管理接口被拒"""
    u = _client_user(db)  # 普通用户
    r = client.post("/api/admin/knowledge",
                    json={"title": "t", "content": "c"}, headers=auth_headers(u))
    assert r.status_code in (401, 403)
    r = client.get("/api/admin/knowledge")
    assert r.status_code in (401, 403)


def test_admin_knowledge_missing_article(client, db):
    """【异常流】更新/删除不存在的知识条目返回 404"""
    u = _client_user(db, role="admin")
    h = auth_headers(u)
    assert client.put("/api/admin/knowledge/999",
                      json={"title": "t", "content": "c"}, headers=h).status_code == 404
    assert client.delete("/api/admin/knowledge/999", headers=h).status_code == 404


# ================= vision 识图 =================

def test_vision_parse_ok_and_invalid():
    """覆盖识图结果解析：合法 JSON、前后带杂文、置信度截断、非法 JSON 抛错"""
    assert vision._parse('{"keywords":"iPhone16 手机","category":"手机","confidence":0.9}')['keywords'] == "iPhone16 手机"
    assert vision._parse('前置文字 {"keywords":"耳机","category":"数码","confidence":1.5} 后置')["confidence"] == 1.0
    import pytest
    with pytest.raises(ValueError):
        vision._parse("完全不是 JSON")


def test_image_search_local_candidates(client, db, monkeypatch):
    """【正常流】识图搜索返回本地库与联网两类候选"""
    p = make_product(db, name="识图测试手机", category="手机")
    make_listing(db, p, current_price=1000.0)
    monkeypatch.setattr("app.services.vision.image_keywords",
                        lambda images, ai_config=None: {"keywords": "识图测试 手机", "category": "手机", "confidence": 0.9})
    monkeypatch.setattr("app.services.crawler.manmanbuy.discover_products",
                        lambda *a, **k: [{"title": "联网同款", "price": 999.0, "platform": "京东",
                                          "url": "https://x", "image": ""}])
    u = _client_user(db)
    r = client.post("/api/advisor/image_search", json={"images": ["data:image/png;base64,x"]},
                    headers=auth_headers(u))
    data = r.json()
    assert data["ok"] is True and data["keywords"] == "识图测试 手机"
    sources = [c["source"] for c in data["candidates"]]
    assert "本地库" in sources and "联网" in sources
    local = next(c for c in data["candidates"] if c["source"] == "本地库")
    assert local["product_id"] == p.id and local["price"] == 1000.0


def test_image_search_live_fail_degrades(client, db, monkeypatch):
    """【降级】联网搜索失败时静默降级为本地候选"""
    # 联网搜索失败 -> 静默降级为本地结果
    monkeypatch.setattr("app.services.vision.image_keywords",
                        lambda images, ai_config=None: {"keywords": "手机", "category": "", "confidence": 0.5})
    monkeypatch.setattr("app.services.crawler.manmanbuy.discover_products",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("登录态失效")))
    u = _client_user(db)
    data = client.post("/api/advisor/image_search", json={"images": ["data:image/png;base64,x"]},
                       headers=auth_headers(u)).json()
    assert data["ok"] is True and all(c["source"] == "本地库" for c in data["candidates"])


def test_image_search_recognize_fail(client, db, monkeypatch):
    """【异常流】图片识别失败时返回错误提示"""
    monkeypatch.setattr("app.services.vision.image_keywords",
                        lambda images, ai_config=None: (_ for _ in ()).throw(RuntimeError("视觉接口失败")))
    u = _client_user(db)
    data = client.post("/api/advisor/image_search", json={"images": ["data:image/png;base64,x"]},
                       headers=auth_headers(u)).json()
    assert data["ok"] is False and "图片识别失败" in data["error"]


def test_image_search_no_keyword(client, db, monkeypatch):
    """【边界】识别不出关键词时返回空候选与提示"""
    monkeypatch.setattr("app.services.vision.image_keywords",
                        lambda images, ai_config=None: {"keywords": "", "category": "", "confidence": 0.1})
    u = _client_user(db)
    data = client.post("/api/advisor/image_search", json={"images": ["data:image/png;base64,x"]},
                       headers=auth_headers(u)).json()
    assert data["ok"] is True and data["candidates"] == [] and "未能识别" in data["message"]
