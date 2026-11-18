# -*- coding: utf-8 -*-
"""MCP 服务端（stdio 传输，JSON-RPC 2.0）：向 Agent/外部 MCP 客户端提供网页获取能力

工具：
- fetch_webpage(url)：抓取网页并提取标题与正文文本（了解商品行情/促销/评测）
- web_search(query)：网页搜索，返回标题/链接/摘要（了解市场动态）

运行：python -m app.services.mcp_server
（mcp_client 自动拉起；也可注册到 Claude Desktop 等任意 MCP 客户端）
协议：按行收发 JSON-RPC 2.0 消息；stdout 只输出协议消息，日志走 stderr。
"""
import json
import sys

from . import web_fetch

SERVER_INFO = {"name": "spt-web-mcp", "version": "1.0.0"}
PROTOCOL_VERSION = "2024-11-05"

TOOLS = [
    {
        "name": "fetch_webpage",
        "description": "抓取指定网页，提取标题与正文文本。用于了解商品行情、促销资讯、评测内容，把握市场动态后给出消费建议。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "要抓取的网页链接（http/https）"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "web_search",
        "description": "按关键词搜索网页，返回标题/链接/摘要。用于查询商品行情、市场动态、促销信息。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词，如：RTX4060 行情、618 手机降价"},
                "limit": {"type": "integer", "description": "返回条数上限，默认 5"},
            },
            "required": ["query"],
        },
    },
]


def call_tool(name: str, arguments: dict) -> dict:
    """执行工具调用 -> MCP tools/call 结果 {content, isError}

    结果按 MCP 规范包装为 content 文本块；未知工具/执行异常均返回 isError=True
    而非抛出，由客户端侧转成错误文本。
    """
    try:
        if name == "fetch_webpage":
            data = web_fetch.fetch_page_text(str(arguments.get("url") or ""))
            text = f"标题：{data['title']}\n来源：{data['url']}\n\n{data['text']}"
        elif name == "web_search":
            items = web_fetch.search_snippets(
                str(arguments.get("query") or ""), int(arguments.get("limit") or 5)
            )
            if not items:
                text = "（未搜索到相关结果）"
            else:
                # 搜索结果拼成编号列表：标题 + 链接 + 摘要
                text = "\n\n".join(
                    f"{i + 1}. {it['title']}\n   {it['url']}\n   {it['snippet']}"
                    for i, it in enumerate(items)
                )
        else:
            return {"content": [{"type": "text", "text": f"未知工具：{name}"}], "isError": True}
        return {"content": [{"type": "text", "text": text}], "isError": False}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"工具执行失败：{e}"}], "isError": True}


def handle_request(msg: dict):
    """处理一条 JSON-RPC 消息，返回响应（notification 返回 None）"""
    method = msg.get("method") or ""
    mid = msg.get("id")
    if method.startswith("notifications/"):
        return None  # 通知类消息无需响应（如 notifications/initialized）
    if method == "initialize":
        # MCP 握手：返回协议版本、能力声明与服务端信息
        return {"jsonrpc": "2.0", "id": mid, "result": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
        }}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": mid, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = msg.get("params") or {}
        result = call_tool(params.get("name") or "", params.get("arguments") or {})
        return {"jsonrpc": "2.0", "id": mid, "result": result}
    if mid is None:
        return None
    # 未知方法：按 JSON-RPC 规范返回 -32601 Method not found
    return {"jsonrpc": "2.0", "id": mid,
            "error": {"code": -32601, "message": f"未知方法：{method}"}}


def main():
    """主循环：按行读取 stdin 的 JSON-RPC 消息，处理后写回 stdout（一行一条）"""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        resp = handle_request(msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
