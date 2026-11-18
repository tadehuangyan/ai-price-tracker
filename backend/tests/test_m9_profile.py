# -*- coding: utf-8 -*-
"""M9 用户画像（个性化消费建议）测试

覆盖目标：user_profile MD 文件读写（分节/去重/截断）、画像上下文组装、
update_user_profile / get_user_profile 工具、画像注入对话、
Agent 流式对话中记录偏好落盘。画像文件写入临时目录，不污染真实存储。
"""
import json as _json
import os

import pytest

from app.services import agent_tools, ai_advisor, user_profile

from conftest import auth_headers, make_user


@pytest.fixture()
def profile_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(user_profile, "PROFILE_DIR", str(tmp_path))
    return tmp_path


def _client_user(db, role="user"):
    return make_user(db, username="pf_user", email="pf@qq.com", role=role)


def _parse_sse(text):
    events = []
    for part in text.split("\n\n"):
        part = part.strip()
        if part.startswith("data:"):
            events.append(_json.loads(part[5:].strip()))
    return events


# ================= MD 文件读写 =================

def test_record_note_creates_md_with_sections(profile_dir):
    r = user_profile.record_note(1, "预算", "预算约 3000 元")
    assert r["ok"] and r["section"] == "预算区间" and not r["duplicated"]
    path = os.path.join(str(profile_dir), "user_1.md")
    assert os.path.exists(path)
    text = user_profile.read_profile(1)
    assert "# 用户画像" in text and "## 预算区间" in text and "- 预算约 3000 元" in text


def test_record_note_dedupe_and_unknown_category(profile_dir):
    user_profile.record_note(1, "偏好", "偏好性价比高的手机")
    r = user_profile.record_note(1, "偏好", "偏好性价比高的手机")
    assert r["duplicated"] is True  # 重复不落盘
    r2 = user_profile.record_note(1, "乱写的类别", "喜欢大屏")
    assert r2["section"] == "消费偏好"  # 未知类别归入消费偏好
    text = user_profile.read_profile(1)
    assert text.count("偏好性价比高的手机") == 1 and "喜欢大屏" in text


def test_record_note_empty_and_truncate(profile_dir):
    assert user_profile.record_note(1, "偏好", "  ")["ok"] is False
    r = user_profile.record_note(1, "偏好", "长" * 300)
    assert len(r["note"]) == user_profile.MAX_NOTE_LEN


def test_build_context_formatting(profile_dir):
    assert user_profile.build_context(1) == ""  # 无画像返回空串
    user_profile.record_note(1, "预算", "预算约 3000 元")
    user_profile.record_note(1, "关注", "关注 iPhone16")
    text = user_profile.build_context(1)
    assert text.startswith("【用户画像】")
    assert "预算区间：预算约 3000 元" in text and "关注商品：关注 iPhone16" in text


def test_sections_round_trip_profile_dir(profile_dir):
    # 多类别多次写入后解析保持分节结构
    for cat, note in [("偏好", "偏好轻薄本"), ("预算", "预算 6000"), ("习惯", "习惯大促囤货"),
                      ("关注", "关注轻薄本")]:
        user_profile.record_note(2, cat, note)
    sections = user_profile._parse_sections(user_profile.read_profile(2))
    assert sections["消费偏好"] == ["偏好轻薄本"]
    assert sections["预算区间"] == ["预算 6000"]
    assert sections["购买习惯"] == ["习惯大促囤货"]
    assert sections["关注商品"] == ["关注轻薄本"]


# ================= Agent 工具 =================

def test_tool_update_and_get_profile(profile_dir, db):
    u = _client_user(db)
    r = _json.loads(agent_tools.dispatch(db, u, "update_user_profile",
                                         _json.dumps({"category": "预算", "note": "预算约 3000 元"})))
    assert r["ok"] and r["section"] == "预算区间"
    data = _json.loads(agent_tools.dispatch(db, u, "get_user_profile", "{}"))
    assert "预算约 3000 元" in data["profile"]


def test_tool_profile_requires_login(profile_dir, db):
    assert "登录" in agent_tools.dispatch(db, None, "update_user_profile",
                                          _json.dumps({"category": "偏好", "note": "x"}))
    assert "登录" in agent_tools.dispatch(db, None, "get_user_profile", "{}")


# ================= 画像注入对话 =================

def test_chat_reply_injects_profile(profile_dir, db, monkeypatch):
    u = _client_user(db)
    user_profile.record_note(u.id, "预算", "预算约 3000 元")
    calls = []
    monkeypatch.setattr(ai_advisor, "llm_chat",
                        lambda messages, **k: calls.append(messages) or "好的")
    ai_advisor.chat_reply(db, "推荐个手机", [], user=u)
    system = calls[0][0]["content"]
    assert "【用户画像】" in system and "预算约 3000 元" in system
    assert "update_user_profile" in system  # Prompt 声明画像记录能力


def test_chat_reply_no_user_no_profile(profile_dir, db, monkeypatch):
    user_profile.record_note(99, "预算", "无关画像")
    calls = []
    monkeypatch.setattr(ai_advisor, "llm_chat",
                        lambda messages, **k: calls.append(messages) or "好的")
    ai_advisor.chat_reply(db, "推荐个手机", [])  # 未登录（user=None）
    assert "无关画像" not in calls[0][0]["content"]  # 他人画像不注入


# ================= 个人中心：查看 / 编辑画像 =================

def test_profile_memo_endpoints(client, db, profile_dir):
    u = _client_user(db)
    h = auth_headers(u)
    assert client.get("/api/auth/profile-memo", headers=h).json()["content"] == ""
    r = client.put("/api/auth/profile-memo",
                   json={"content": "# 用户画像\n\n## 消费偏好\n- 喜欢安静\n"}, headers=h)
    assert r.json()["ok"] is True
    assert "喜欢安静" in client.get("/api/auth/profile-memo", headers=h).json()["content"]
    assert "喜欢安静" in user_profile.read_profile(u.id)  # 真实落盘到画像 MD


def test_profile_memo_requires_login(client, db, profile_dir):
    assert client.get("/api/auth/profile-memo").status_code in (401, 403)
    assert client.put("/api/auth/profile-memo", json={"content": "x"}).status_code in (401, 403)


def test_record_note_preserves_free_form(db, profile_dir):
    # 用户手编的自由内容（标题/备注）不会被 Agent 记录覆盖
    user_profile.write_profile(1, "# 我的自定义标题\n\n随便写的备注\n\n## 消费偏好\n- 老条目\n")
    user_profile.record_note(1, "偏好", "新条目")
    text = user_profile.read_profile(1)
    assert "我的自定义标题" in text and "随便写的备注" in text
    assert "老条目" in text and "新条目" in text


# ================= Agent 对话中记录偏好（流式） =================

def test_stream_agent_records_preference(client, db, monkeypatch, profile_dir):
    u = _client_user(db)
    calls = []

    def fake_stream(messages, tools=None, temperature=0.6, timeout=90, ai_config=None):
        calls.append(bool(tools))
        if len(calls) == 1:  # 首轮记录偏好，工具结果回填后第二轮作答
            yield {"type": "tool_calls", "calls": [{
                "id": "c1", "name": "update_user_profile",
                "arguments": _json.dumps({"category": "偏好", "note": "偏好性价比高的手机"}),
            }]}
        else:
            yield {"type": "text", "text": "已记住你的偏好，下次推荐更贴合"}

    monkeypatch.setattr(ai_advisor, "llm_stream_ex", fake_stream)
    r = client.post("/api/advisor/chat/stream",
                    json={"message": "我比较喜欢性价比高的手机，帮我留意下"},
                    headers=auth_headers(u))
    events = _parse_sse(r.text)
    tools = [e for e in events if e["type"] == "tool"]
    assert tools and tools[-1]["name"] == "update_user_profile" and tools[-1]["status"] == "done"
    text = user_profile.read_profile(u.id)
    assert "偏好性价比高的手机" in text  # 已写入画像 MD 文件
