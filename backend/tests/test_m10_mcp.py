# -*- coding: utf-8 -*-
"""M10 MCP 网页获取 测试

覆盖目标：web_fetch URL 安全校验与正文/搜索结果解析、mcp_server JSON-RPC 协议
（initialize/tools/list/tools/call）、mcp_client stdio 子进程端到端往返、
agent_tools 经 MCP 的 web_search / fetch_webpage 工具链（含失败降级）。
网络请求在接口边界 mock，stdio 往返用真实子进程但不触网。
"""
import json as _json
from types import SimpleNamespace

import pytest

from app.services import agent_tools, mcp_client, mcp_server, web_fetch

from conftest import auth_headers, make_user


# ================= web_fetch =================

def test_validate_url_security():
    assert web_fetch.validate_url("https://item.jd.com/1.html") == "https://item.jd.com/1.html"
    for bad in ("ftp://x.com/a", "file:///etc/passwd", "http://localhost:8000/a",
                "http://127.0.0.1/a", "http://192.168.1.1/a", "http://10.0.0.5/a", "not a url"):
        with pytest.raises(ValueError):
            web_fetch.validate_url(bad)


def test_html_to_text_extracts_title_and_body():
    page = """<html><head><title>显卡行情</title><style>.x{}</style>
    <script>alert(1)</script></head><body><h1>RTX4060</h1>
    <p>本周价格持续走低。</p><p>预计仍有下降空间。</p></body></html>"""
    title, text = web_fetch.html_to_text(page)
    assert title == "显卡行情"
    assert "RTX4060" in text and "本周价格持续走低。" in text
    assert "alert" not in text and "<p>" not in text


def test_fetch_page_text(monkeypatch):
    fake = lambda url, **k: SimpleNamespace(
        text="<html><head><title>行情</title></head><body><p>内容</p></body></html>",
        url="https://example.com/p", raise_for_status=lambda: None)
    monkeypatch.setattr("app.services.web_fetch.httpx.get", fake)
    data = web_fetch.fetch_page_text("https://example.com/p")
    assert data["title"] == "行情" and "内容" in data["text"]


def test_search_snippets_parses_results(monkeypatch):
    html = """<html><body>
    <li class="b_algo"><h2><a href="https://example.com/a">显卡行情</a></h2><p>RTX4060 价格走低</p></li>
    <li class="b_algo"><h2><a href="https://example.com/b">手机降价榜</a></h2><p>618 促销开启</p></li>
    </body></html>"""
    monkeypatch.setattr("app.services.web_fetch.httpx.get",
                        lambda url, **k: SimpleNamespace(text=html, url=url, raise_for_status=lambda: None))
    items = web_fetch.search_snippets("显卡 行情", limit=5)
    assert len(items) == 2 and items[0]["title"] == "显卡行情"
    assert items[0]["url"] == "https://example.com/a" and "价格走低" in items[0]["snippet"]


def test_search_snippets_empty(monkeypatch):
    monkeypatch.setattr("app.services.web_fetch.httpx.get",
                        lambda url, **k: SimpleNamespace(text="<html></html>", url=url, raise_for_status=lambda: None))
    assert web_fetch.search_snippets("xxx") == []
    with pytest.raises(ValueError):
        web_fetch.search_snippets("  ")


# ================= mcp_server JSON-RPC 协议 =================

def test_mcp_server_initialize_and_list_tools():
    resp = mcp_server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert resp["result"]["serverInfo"]["name"] == "spt-web-mcp"
    assert resp["result"]["protocolVersion"] == mcp_server.PROTOCOL_VERSION
    tools = mcp_server.handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = {t["name"] for t in tools["result"]["tools"]}
    assert {"fetch_webpage", "web_search"} <= names


def test_mcp_server_notifications_and_unknown_method():
    assert mcp_server.handle_request({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    resp = mcp_server.handle_request({"jsonrpc": "2.0", "id": 3, "method": "foo/bar"})
    assert resp["error"]["code"] == -32601


def test_mcp_server_tools_call(monkeypatch):
    monkeypatch.setattr("app.services.web_fetch.fetch_page_text",
                        lambda url: {"title": "行情", "text": "正文", "url": url})
    resp = mcp_server.handle_request({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                                      "params": {"name": "fetch_webpage", "arguments": {"url": "https://x"}}})
    result = resp["result"]
    assert result["isError"] is False and "行情" in result["content"][0]["text"]
    # 未知工具 -> isError（无需 mock，直接走分发）
    resp2 = mcp_server.handle_request({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                                       "params": {"name": "hack", "arguments": {}}})
    assert resp2["result"]["isError"] is True


def test_mcp_server_tools_call_rejects_bad_url():
    # URL 校验拦截（真实 web_fetch，不触网：校验先于请求失败）
    resp = mcp_server.handle_request({"jsonrpc": "2.0", "id": 6, "method": "tools/call",
                                      "params": {"name": "fetch_webpage", "arguments": {"url": "ftp://x"}}})
    assert resp["result"]["isError"] is True


# ================= mcp_client stdio 端到端 =================

def test_mcp_client_stdio_list_tools():
    tools = mcp_client.list_tools()  # 真实子进程 + JSON-RPC 握手（不触网）
    names = {t["name"] for t in tools}
    assert {"fetch_webpage", "web_search"} <= names
    mcp_client.mcp.close()


def test_mcp_client_stdio_call_tool_error():
    with pytest.raises(mcp_client.McpError):
        mcp_client.call_tool("fetch_webpage", {"url": "ftp://bad"})  # 服务端校验失败 -> isError
    mcp_client.mcp.close()


# ================= agent_tools 经 MCP 的工具链 =================

def test_agent_tool_web_search_via_mcp(db, monkeypatch):
    monkeypatch.setattr("app.services.mcp_client.call_tool",
                        lambda name, args: f"{name}:{args['query']}")
    data = _json.loads(agent_tools.dispatch(db, None, "web_search",
                                            _json.dumps({"query": "显卡行情"})))
    assert data["ok"] is True and data["content"] == "web_search:显卡行情"
    assert "缺少 query" in agent_tools.dispatch(db, None, "web_search", "{}")


def test_agent_tool_fetch_webpage_via_mcp(db, monkeypatch):
    monkeypatch.setattr("app.services.mcp_client.call_tool", lambda name, args: "网页正文")
    data = _json.loads(agent_tools.dispatch(db, None, "fetch_webpage",
                                            _json.dumps({"url": "https://x"})))
    assert data["ok"] is True and data["content"] == "网页正文"
    assert "缺少 url" in agent_tools.dispatch(db, None, "fetch_webpage", "{}")


def test_agent_tool_mcp_failure_degrades(db, monkeypatch):
    def boom(name, args):
        raise mcp_client.McpError("连接已关闭")
    monkeypatch.setattr("app.services.mcp_client.call_tool", boom)
    data = _json.loads(agent_tools.dispatch(db, None, "web_search",
                                            _json.dumps({"query": "行情"})))
    assert data["error"] and "MCP" in data["error"]  # 错误回填给模型，不中断对话


# ================= Agent 对话中主动查行情（流式） =================

def test_stream_agent_web_search(client, db, monkeypatch):
    from app.services import ai_advisor

    u = make_user(db, username="mcp_user", email="mcp@qq.com")
    monkeypatch.setattr("app.services.mcp_client.call_tool",
                        lambda name, args: "1. 行情：显卡价格持续走低\n   https://x")
    calls = []

    def fake_stream(messages, tools=None, temperature=0.6, timeout=90, ai_config=None):
        calls.append(bool(tools))
        if len(calls) == 1:  # 首轮请求调用工具，工具结果回填后第二轮作答
            yield {"type": "tool_calls", "calls": [{
                "id": "c1", "name": "web_search",
                "arguments": _json.dumps({"query": "显卡行情"}),
            }]}
        else:
            yield {"type": "text", "text": "根据行情，显卡价格走低，建议可以入手"}

    monkeypatch.setattr(ai_advisor, "llm_stream_ex", fake_stream)
    r = client.post("/api/advisor/chat/stream",
                    json={"message": "帮我查下现在显卡行情怎么样"}, headers=auth_headers(u))
    events = []
    for part in r.text.split("\n\n"):
        part = part.strip()
        if part.startswith("data:"):
            events.append(_json.loads(part[5:].strip()))
    tools = [e for e in events if e["type"] == "tool"]
    assert tools and tools[-1]["name"] == "web_search" and tools[-1]["status"] == "done"
    text = "".join(e.get("text", "") for e in events if e.get("type") == "delta")
    assert "显卡价格走低" in text
