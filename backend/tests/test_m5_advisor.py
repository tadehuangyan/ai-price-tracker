# -*- coding: utf-8 -*-
"""M5 AI 智能导购 测试（ai.py + ai_advisor.py + moderation.py）

覆盖目标：输入/输出敏感词过滤、聊天上下文组装（商品/链接/图片/文件）、
大模型调用与降级链、模型配置选择、文件上传的语句与条件覆盖。
大模型与爬虫在接口边界 mock，不发起真实网络请求。
"""
import io
from datetime import datetime, timedelta

import pytest

from app.models import SensitiveWord
from app.services import ai_advisor, moderation

from conftest import auth_headers, make_listing, make_product, make_snapshot, make_user


# ================= moderation 敏感词过滤 =================

def _add_word(db, word, category="通用", enabled=True):
    db.add(SensitiveWord(word=word, category=category, enabled=enabled))
    db.commit()


def test_find_sensitive_empty_text(db):
    assert moderation.find_sensitive("", db) == []
    assert moderation.find_sensitive(None, db) == []


def test_find_sensitive_hit_case_insensitive(db):
    _add_word(db, "赌博")
    _add_word(db, "Scam")
    hits = moderation.find_sensitive("参与赌博 and SCAM activity", db)
    assert set(hits) == {"赌博", "Scam"}  # 大小写不敏感的子串匹配


def test_find_sensitive_no_hit(db):
    _add_word(db, "赌博")
    assert moderation.find_sensitive("正常购物咨询", db) == []


def test_find_sensitive_skips_blank_and_disabled_words(db):
    # 启用过滤 + strip 后为空的词跳过
    _add_word(db, "  ", enabled=True)
    _add_word(db, "违禁词", enabled=False)
    assert moderation.find_sensitive("这里有违禁词吗", db) == []


def test_get_words_cache_and_invalidate(db):
    _add_word(db, "词A")
    w1 = moderation.get_words(db)
    assert w1 == ["词A"]
    # 缓存期内新增词不可见（缓存命中分支）
    db.add(SensitiveWord(word="词B"))
    db.commit()
    assert moderation.get_words(db) == ["词A"]
    # invalidate_cache 后立即生效（缓存失效分支）
    moderation.invalidate_cache()
    assert set(moderation.get_words(db)) == {"词A", "词B"}


# ================= 聊天接口：敏感词与模型配置 =================

def _client_user(db):
    return make_user(db, username="ai_user", email="ai@qq.com")


def test_check_text_blocked(client, db):
    _add_word(db, "赌博")
    u = _client_user(db)
    r = client.post("/api/advisor/check", json={"text": "帮我赌博下注"}, headers=auth_headers(u))
    data = r.json()
    assert data["ok"] is True and data["blocked"] is True and "赌博" in data["hits"]


def test_check_text_pass(client, db):
    _add_word(db, "赌博")
    u = _client_user(db)
    r = client.post("/api/advisor/check", json={"text": "推荐个手机"}, headers=auth_headers(u))
    data = r.json()
    assert data["ok"] is True and data["blocked"] is False and data["hits"] == []


def test_check_text_requires_login(client, db):
    r = client.post("/api/advisor/check", json={"text": "hi"})
    assert r.status_code == 401


def test_chat_input_sensitive_blocked_without_llm(client, db, monkeypatch):
    _add_word(db, "赌博")
    monkeypatch.setattr(ai_advisor, "llm_chat",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("不应调用大模型")))
    u = _client_user(db)
    r = client.post("/api/advisor/chat", json={"message": "帮我赌博下注"},
                    headers=auth_headers(u))
    data = r.json()
    assert data["ok"] is False and "敏感词" in data["error"] and "赌博" in data["error"]


# ================= 流式聊天接口（SSE） =================

import json as _json


def _parse_sse(text):
    events = []
    for part in text.split("\n\n"):
        part = part.strip()
        if part.startswith("data:"):
            events.append(_json.loads(part[5:].strip()))
    return events


def _deltas_text(events):
    return "".join(e.get("text", "") for e in events if e.get("type") == "delta")


def test_chat_stream_normal(client, db, monkeypatch):
    monkeypatch.setattr(ai_advisor, "llm_chat_stream", lambda *a, **k: iter(["你好，", "建议购买"]))
    u = _client_user(db)
    r = client.post("/api/advisor/chat/stream", json={"message": "值得买吗"}, headers=auth_headers(u))
    events = _parse_sse(r.text)
    assert _deltas_text(events) == "你好，建议购买"
    assert events[-1]["type"] == "done" and events[-1]["fallback"] is False


def test_chat_stream_input_sensitive_json_error(client, db):
    _add_word(db, "赌博")
    u = _client_user(db)
    r = client.post("/api/advisor/chat/stream", json={"message": "帮我赌博"}, headers=auth_headers(u))
    data = r.json()
    assert data["ok"] is False and "敏感词" in data["error"]


def test_chat_stream_output_blocked_across_chunks(client, db, monkeypatch):
    # 敏感词跨 chunk（"介绍枪" + "支商品"）：回看窗口拦截，输出中不含完整敏感词
    _add_word(db, "枪支")
    monkeypatch.setattr(ai_advisor, "llm_chat_stream", lambda *a, **k: iter(["介绍枪", "支商品给你"]))
    u = _client_user(db)
    r = client.post("/api/advisor/chat/stream", json={"message": "介绍下"}, headers=auth_headers(u))
    events = _parse_sse(r.text)
    from app.routers.ai import BLOCKED_REPLY
    assert events[-1]["type"] == "blocked" and events[-1]["reply"] == BLOCKED_REPLY
    assert "枪支" not in _deltas_text(events)


def test_chat_stream_midstream_error_keeps_partial(client, db, monkeypatch):
    def gen():
        yield "前半段"
        raise RuntimeError("连接中断")

    monkeypatch.setattr(ai_advisor, "llm_chat_stream", lambda *a, **k: gen())
    u = _client_user(db)
    r = client.post("/api/advisor/chat/stream", json={"message": "测试"}, headers=auth_headers(u))
    events = _parse_sse(r.text)
    assert _deltas_text(events) == "前半段"  # 尾段补发，不丢已生成内容
    assert events[-1]["type"] == "error" and "连接中断" in events[-1]["message"]


def test_chat_stream_fallback_summary_with_context(client, db, monkeypatch):
    monkeypatch.setattr(ai_advisor, "llm_chat_stream",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("接口失败")))
    p = make_product(db, name="流式手机", category="手机")
    make_listing(db, p, current_price=1000.0)
    u = _client_user(db)
    r = client.post("/api/advisor/chat/stream",
                    json={"message": "[[product:%d]]怎么样" % p.id}, headers=auth_headers(u))
    events = _parse_sse(r.text)
    assert events[-1]["type"] == "done" and events[-1]["fallback"] is True
    assert "AI 服务暂时不可用" in _deltas_text(events) and "流式手机" in _deltas_text(events)


def test_chat_stream_fallback_no_context_custom_model(client, db, monkeypatch):
    monkeypatch.setattr(ai_advisor, "llm_chat_stream",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("接口失败")))
    u = _client_user(db)
    cfg = {"api_base": "https://api.x.com", "api_key": "k", "model": "m"}
    r = client.post("/api/advisor/chat/stream",
                    json={"message": "随便聊聊", "ai_config": cfg}, headers=auth_headers(u))
    events = _parse_sse(r.text)
    assert events[-1]["type"] == "done" and events[-1]["fallback"] is True
    assert "自定义模型调用失败" in _deltas_text(events)


def test_chat_stream_images_retry_text_only(client, db, monkeypatch):
    # 多模态失败 -> 纯文本重试成功，附注图片未解析
    calls = []

    def fake(*a, **k):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("视觉接口失败")
        return iter(["文字回复"])

    monkeypatch.setattr(ai_advisor, "llm_chat_stream", fake)
    u = _client_user(db)
    r = client.post("/api/advisor/chat/stream",
                    json={"message": "看图", "images": ["data:image/png;base64,xx"]},
                    headers=auth_headers(u))
    events = _parse_sse(r.text)
    assert events[-1]["type"] == "done" and events[-1]["fallback"] is False
    text = _deltas_text(events)
    assert "文字回复" in text and "图片未能被模型解析" in text


def test_chat_stream_config_incomplete(client, db):
    u = _client_user(db)
    r = client.post("/api/advisor/chat/stream",
                    json={"message": "hi", "ai_config": {"api_base": "", "api_key": "k", "model": "m"}},
                    headers=auth_headers(u))
    data = r.json()
    assert data["ok"] is False and "配置不完整" in data["error"]


def test_chat_ai_config_incomplete(client, db, monkeypatch):
    monkeypatch.setattr(ai_advisor, "llm_chat",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("不应调用大模型")))
    u = _client_user(db)
    for cfg in ({"api_base": "https://api.x.com", "api_key": "", "model": "m"},
                {"api_base": "   ", "api_key": "k", "model": "m"}):
        r = client.post("/api/advisor/chat", json={"message": "推荐个手机", "ai_config": cfg},
                        headers=auth_headers(u))
        assert r.json()["ok"] is False and "配置不完整" in r.json()["error"]


def test_chat_ai_config_complete_ok(client, db, monkeypatch):
    seen = {}

    def fake_llm(messages, temperature=0.5, timeout=60, json_mode=False, ai_config=None):
        seen["ai_config"] = ai_config
        return "自定义模型回复"

    monkeypatch.setattr(ai_advisor, "llm_chat", fake_llm)
    u = _client_user(db)
    cfg = {"api_base": "https://api.x.com", "api_key": "k", "model": "my-model"}
    r = client.post("/api/advisor/chat", json={"message": "推荐个手机", "ai_config": cfg},
                    headers=auth_headers(u))
    data = r.json()
    assert data["ok"] is True and data["reply"] == "自定义模型回复" and data["fallback"] is False
    assert seen["ai_config"] == cfg


def test_chat_output_sensitive_blocked(client, db, monkeypatch):
    _add_word(db, "枪支")
    monkeypatch.setattr(ai_advisor, "llm_chat", lambda *a, **k: "这里有枪支出售信息")
    u = _client_user(db)
    r = client.post("/api/advisor/chat", json={"message": "介绍下商品"}, headers=auth_headers(u))
    data = r.json()
    from app.routers.ai import BLOCKED_REPLY
    assert data["ok"] is True and data["blocked"] is True and data["reply"] == BLOCKED_REPLY
    assert data["fallback"] is False


def test_chat_ok_default_model(client, db, monkeypatch):
    monkeypatch.setattr(ai_advisor, "llm_chat", lambda *a, **k: "建议立即购买")
    u = _client_user(db)
    r = client.post("/api/advisor/chat", json={"message": "值得买吗"}, headers=auth_headers(u))
    data = r.json()
    assert data["ok"] is True and data["reply"] == "建议立即购买" and data["fallback"] is False


# ================= chat_reply 上下文组装 =================

def _fake_llm_capture(calls):
    def fake(messages, temperature=0.5, timeout=60, json_mode=False, ai_config=None):
        calls.append(messages)
        return "好的回复"
    return fake


def _product_with_history(db):
    p = make_product(db, name="上下文手机", category="手机")
    l = make_listing(db, p, current_price=1000.0)
    make_listing(db, p, platform="taobao", url="https://t/ctx", current_price=1200.0)  # 多平台报价
    base = datetime(2026, 7, 1)
    for i in range(15):
        make_snapshot(db, l, 1000.0 + i, base + timedelta(days=i))
    make_snapshot(db, l, 9999.0, base + timedelta(hours=12))  # 同日更高 -> 不更新的分支
    return p


def test_chat_reply_product_tag(db, monkeypatch):
    p = _product_with_history(db)
    calls = []
    monkeypatch.setattr(ai_advisor, "llm_chat", _fake_llm_capture(calls))
    out = ai_advisor.chat_reply(db, "[[product:%d]]值得买吗" % p.id, [])
    assert out["fallback"] is False
    ctx = out["contexts"][0]
    assert "上下文手机" in ctx and "当前价" in ctx and "历史最低" in ctx and "趋势" in ctx
    assert "多平台报价" in ctx  # 多报价分支
    # 商品标记被替换为展示名
    assert "【商品：上下文手机】" in calls[0][-1]["content"]


def test_chat_reply_product_tag_single_offer(db, monkeypatch):
    # 单报价商品 -> 不输出多平台报价行的分支
    p = make_product(db, name="单报价手机", category="手机")
    make_listing(db, p, current_price=500.0)
    calls = []
    monkeypatch.setattr(ai_advisor, "llm_chat", _fake_llm_capture(calls))
    out = ai_advisor.chat_reply(db, "[[product:%d]]好吗" % p.id, [])
    assert "多平台报价" not in out["contexts"][0] and "当前价" in out["contexts"][0]


def test_chat_reply_product_tag_invalid(db, monkeypatch):
    # 不存在的商品标记 -> brief 为空 -> 不产生上下文、保留原文
    calls = []
    monkeypatch.setattr(ai_advisor, "llm_chat", _fake_llm_capture(calls))
    out = ai_advisor.chat_reply(db, "[[product:99999]]怎么样", [])
    assert out["contexts"] == []
    # 用户消息经 <user_message> 标签隔离（提示注入防御），原文保留在标签内
    assert "[[product:99999]]怎么样" in calls[0][-1]["content"]
    assert "<user_message>" in calls[0][-1]["content"]


def test_chat_reply_link_ok(db, monkeypatch):
    monkeypatch.setattr("app.services.crawler.manmanbuy.query_history",
                        lambda url, timeout_ms=0: {
                            "title": "链接商品", "site_name": "京东", "price": 99.0,
                            "history": [("2026-01-01", 88.0)], "history_min": 88.0,
                        })
    calls = []
    monkeypatch.setattr(ai_advisor, "llm_chat", _fake_llm_capture(calls))
    out = ai_advisor.chat_reply(db, "看看这个 https://item.jd.com/1.html 值得买吗", [])
    assert "已抓取详情" in out["contexts"][0] and "历史最低" in out["contexts"][0]


def test_chat_reply_link_no_history(db, monkeypatch):
    # 链接抓取成功但无历史价格 -> _link_brief 的空历史分支
    monkeypatch.setattr("app.services.crawler.manmanbuy.query_history",
                        lambda url, timeout_ms=0: {
                            "title": "链接商品", "site_name": "淘宝", "price": 50.0,
                            "history": [], "history_min": None,
                        })
    calls = []
    monkeypatch.setattr(ai_advisor, "llm_chat", _fake_llm_capture(calls))
    out = ai_advisor.chat_reply(db, "https://item.taobao.com/1.html 这个呢", [])
    assert "已抓取详情" in out["contexts"][0] and "历史最低" not in out["contexts"][0]


def test_chat_reply_link_fail(db, monkeypatch):
    def boom(url, timeout_ms=0):
        raise RuntimeError("抓取超时")

    monkeypatch.setattr("app.services.crawler.manmanbuy.query_history", boom)
    calls = []
    monkeypatch.setattr(ai_advisor, "llm_chat", _fake_llm_capture(calls))
    out = ai_advisor.chat_reply(db, "https://item.jd.com/err.html 帮我看看", [])
    assert "抓取失败" in out["contexts"][0]


def test_chat_reply_routed_product_missing(db, monkeypatch):
    # 路由商品不存在 -> brief 为空 -> 不产生上下文的分支
    calls = []
    monkeypatch.setattr(ai_advisor, "llm_chat", _fake_llm_capture(calls))
    out = ai_advisor.chat_reply(db, "看下这个", [], product_id=99999)
    assert out["contexts"] == []


def test_chat_reply_url_appended_when_missing_from_display(db, monkeypatch):
    # 防御性分支：URL 不在展示内容中时补注到上下文（L224）。
    # 正常流程 display 始终包含 URL，此处将商品标记正则替换为会连同 URL 一并
    # 匹配的变体，使 URL 被 sub 移除，从而强制覆盖该分支。
    import re

    p = _product_with_history(db)
    monkeypatch.setattr(ai_advisor, "PRODUCT_TAG_RE",
                        re.compile(r"https?://\S+?\[\[product:(\d+)\]\]"))
    calls = []
    monkeypatch.setattr(ai_advisor, "llm_chat", _fake_llm_capture(calls))
    ai_advisor.chat_reply(db, "https://item.jd.com/9.html[[product:%d]] 如何" % p.id, [])
    assert "（链接：https://item.jd.com/9.html[[product:%d]]）" % p.id in calls[0][-1]["content"]


def test_chat_reply_routed_product_and_history_filter(db, monkeypatch):
    p = _product_with_history(db)
    calls = []
    monkeypatch.setattr(ai_advisor, "llm_chat", _fake_llm_capture(calls))
    history = [{"role": "user", "content": f"历史{i}"} for i in range(8)]
    history += [{"role": "system", "content": "无效角色"}, {"role": "user", "content": ""}]
    ai_advisor.chat_reply(db, "这个手机怎么样", history, product_id=p.id)
    msgs = calls[0]
    # [system(+商品上下文)] + 8 条合法历史 + 当前消息
    assert msgs[0]["role"] == "system" and "当前浏览的商品" in msgs[0]["content"]
    contents = [m["content"] for m in msgs[1:-1]]
    assert contents == [f"历史{i}" for i in range(8)]  # 超出 10 条窗口及非法条目被过滤


def test_chat_reply_images_and_files(db, monkeypatch):
    calls = []
    monkeypatch.setattr(ai_advisor, "llm_chat", _fake_llm_capture(calls))
    out = ai_advisor.chat_reply(
        db, "看下这张图", [],
        images=[f"data:image/png;base64,{i}" for i in range(5)],
        files=[{"name": "清单.docx", "url": "/uploads/1.docx"}],
    )
    assert any("5 张图片" in c for c in out["contexts"])
    assert any("清单.docx" in c for c in out["contexts"])
    user_msg = calls[0][-1]
    # 多模态消息：1 个文本 + 最多 4 张图
    assert isinstance(user_msg["content"], list)
    assert len([c for c in user_msg["content"] if c["type"] == "image_url"]) == 4
    assert "[文件：清单.docx]" in user_msg["content"][0]["text"]


def test_chat_reply_no_images_text_message(db, monkeypatch):
    calls = []
    monkeypatch.setattr(ai_advisor, "llm_chat", _fake_llm_capture(calls))
    ai_advisor.chat_reply(db, "纯文本问题", [])
    # 用户消息经 <user_message> 标签隔离（提示注入防御）
    assert calls[0][-1]["content"].strip() == "<user_message>\n纯文本问题\n</user_message>"


# ================= 降级链 =================

def test_fallback_images_retry_text_ok(db, monkeypatch):
    seq = [RuntimeError("视觉接口失败"), "文字回复"]
    monkeypatch.setattr(ai_advisor, "llm_chat", lambda *a, **k: _pop(seq))
    out = ai_advisor.chat_reply(db, "看图", [], images=["data:image/png;base64,xx"])
    assert out["fallback"] is False
    assert "图片未能被模型解析" in out["reply"]


def test_fallback_images_retry_also_fails_with_context(db, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("全部失败")

    monkeypatch.setattr(ai_advisor, "llm_chat", boom)
    p = _product_with_history(db)
    out = ai_advisor.chat_reply(db, "[[product:%d]]看图" % p.id, [], images=["data:image/png;base64,xx"])
    assert out["fallback"] is True and "AI 服务暂时不可用，以下是已获取的数据" in out["reply"]


def test_fallback_no_images_with_context(db, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("接口失败")

    monkeypatch.setattr(ai_advisor, "llm_chat", boom)
    p = _product_with_history(db)
    out = ai_advisor.chat_reply(db, "[[product:%d]]怎么样" % p.id, [])
    assert out["fallback"] is True and "AI 服务暂时不可用，以下是已获取的数据" in out["reply"]


def test_fallback_no_context_default_model(db, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("接口失败")

    monkeypatch.setattr(ai_advisor, "llm_chat", boom)
    out = ai_advisor.chat_reply(db, "随便聊聊", [])
    assert out["fallback"] is True
    assert "AI 服务暂时不可用（接口失败），请稍后重试" in out["reply"]


def test_fallback_no_context_custom_model(db, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("接口失败")

    monkeypatch.setattr(ai_advisor, "llm_chat", boom)
    cfg = {"api_base": "https://api.x.com", "api_key": "k", "model": "m"}
    out = ai_advisor.chat_reply(db, "随便聊聊", [], ai_config=cfg)
    assert "自定义模型调用失败（接口失败），可在模型设置中修改配置或切回默认模型" in out["reply"]


def _pop(seq):
    v = seq.pop(0)
    if isinstance(v, Exception):
        raise v
    return v


# ================= llm_chat 调用封装 =================

class _Resp:
    def __init__(self, content):
        self._content = content

    def raise_for_status(self):
        pass

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


def test_llm_chat_custom_config_overrides(monkeypatch):
    seen = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        seen.update(url=url, json=json, headers=headers)
        return _Resp("ok")

    monkeypatch.setattr(ai_advisor.httpx, "post", fake_post)
    monkeypatch.setattr(ai_advisor, "LLM_API_BASE", "https://default.api")
    monkeypatch.setattr(ai_advisor, "LLM_API_KEY", "default-key")
    monkeypatch.setattr(ai_advisor, "LLM_MODEL", "default-model")
    out = ai_advisor.llm_chat(
        [{"role": "user", "content": "hi"}],
        ai_config={"api_base": "https://custom.api/", "api_key": "custom-key", "model": "custom-model"},
    )
    assert out == "ok"
    assert seen["url"] == "https://custom.api/chat/completions"  # 尾斜杠规整
    assert seen["json"]["model"] == "custom-model"
    assert seen["headers"]["Authorization"] == "Bearer custom-key"


def test_llm_chat_default_config_and_json_mode(monkeypatch):
    seen = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        seen.update(url=url, json=json)
        return _Resp("{}")

    monkeypatch.setattr(ai_advisor.httpx, "post", fake_post)
    monkeypatch.setattr(ai_advisor, "LLM_API_BASE", "https://default.api")
    monkeypatch.setattr(ai_advisor, "LLM_API_KEY", "default-key")
    monkeypatch.setattr(ai_advisor, "LLM_MODEL", "default-model")
    out = ai_advisor.llm_chat([{"role": "user", "content": "hi"}], json_mode=True)
    assert out == "{}"
    assert seen["url"] == "https://default.api/chat/completions"
    assert seen["json"]["model"] == "default-model"
    assert seen["json"]["response_format"] == {"type": "json_object"}


def test_llm_chat_missing_key_raises(monkeypatch):
    monkeypatch.setattr(ai_advisor, "LLM_API_BASE", "")
    monkeypatch.setattr(ai_advisor, "LLM_API_KEY", "")
    with pytest.raises(RuntimeError, match="LLM_API_KEY"):
        ai_advisor.llm_chat([{"role": "user", "content": "hi"}])
    # key 有值但 base 缺失 -> or 条件另一侧为真
    monkeypatch.setattr(ai_advisor, "LLM_API_KEY", "some-key")
    with pytest.raises(RuntimeError, match="LLM_API_KEY"):
        ai_advisor.llm_chat([{"role": "user", "content": "hi"}])


# ================= build_context =================

def test_build_context_missing_product(db):
    with pytest.raises(ValueError):
        ai_advisor.build_context(db, 99999)


def test_build_context_rising_trend(db):
    p = _product_with_history(db)  # 15 天：1000..1014，近 7 天高于前 7 天不足 2% -> 平稳
    ctx = ai_advisor.build_context(db, p.id)
    assert ctx["trend"] == "平稳" and ctx["percentile"] is not None
    assert ctx["current_price"] == 1000.0  # 取自最低报价


def test_build_context_sharp_rise_and_fall(db):
    # 上涨 > 2%
    p1 = make_product(db, name="上涨商品", category="数码")
    l1 = make_listing(db, p1, current_price=0.0)  # 无有效报价 -> current 取最后快照价
    for i in range(14):
        make_snapshot(db, l1, 100.0 if i < 7 else 150.0, datetime(2026, 3, 1) + timedelta(days=i))
    ctx1 = ai_advisor.build_context(db, p1.id)
    assert ctx1["trend"].startswith("上涨") and ctx1["current_price"] == 150.0
    # 下降 < -2%
    p2 = make_product(db, name="下降商品", category="数码")
    l2 = make_listing(db, p2, current_price=0.0)
    for i in range(14):
        make_snapshot(db, l2, 100.0 if i < 7 else 50.0, datetime(2026, 3, 1) + timedelta(days=i))
    ctx2 = ai_advisor.build_context(db, p2.id)
    assert ctx2["trend"].startswith("下降")


def test_build_context_prev_avg_zero_and_empty_history(db):
    # p > 0 条件为假 -> 平稳；无任何快照 -> 统计全 None
    p1 = make_product(db, name="零价序列", category="数码")
    l1 = make_listing(db, p1, current_price=0.0)
    for i in range(14):
        make_snapshot(db, l1, 0.0 if i < 7 else 10.0, datetime(2026, 3, 1) + timedelta(days=i))
    assert ai_advisor.build_context(db, p1.id)["trend"] == "平稳"
    p2 = make_product(db, name="空历史", category="数码")
    ctx2 = ai_advisor.build_context(db, p2.id)
    assert ctx2["current_price"] is None and ctx2["history_min"] is None
    assert ctx2["history_avg"] is None and ctx2["percentile"] is None


# ================= 文件上传 =================

def test_upload_requires_login(client, db):
    r = client.post("/api/advisor/upload", files={"file": ("a.txt", b"x")})
    assert r.status_code == 401


def test_upload_sanitizes_filename(client, db):
    u = make_user(db, username="up1", email="up1@qq.com")
    r = client.post("/api/advisor/upload",
                    files={"file": ("测试 file!.txt", io.BytesIO(b"hello"))},
                    headers=auth_headers(u))
    data = r.json()
    assert data["ok"] is True and data["name"] == "测试 file!.txt"
    assert data["url"].startswith("/uploads/") and data["url"].endswith(".txt")
    assert " " not in data["url"] and "!" not in data["url"]


def test_upload_filename_none_fallback(db):
    # filename 缺省 -> 安全名回退为 file
    from app.routers.ai import upload_file

    fake = type("F", (), {"filename": None, "file": io.BytesIO(b"x")})()
    out = upload_file(file=fake, _=None)
    assert out["url"].split("_", 1)[1] == "file"
