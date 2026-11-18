# -*- coding: utf-8 -*-
"""MCP 客户端（stdio）：拉起本地 MCP 服务端子进程，按 JSON-RPC 2.0 调用工具

Agent 的 fetch_webpage / web_search 通过本客户端走 MCP 协议获取网页信息；
MCP 通道不可用时抛 McpError（由上层工具降级提示，不中断对话）。
"""
import json
import os
import subprocess
import sys
import threading

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROTOCOL_VERSION = "2024-11-05"
CLIENT_INFO = {"name": "spt-agent", "version": "1.0.0"}


class McpError(RuntimeError):
    """MCP 调用失败（连接/协议/工具错误）"""


class McpClient:
    """stdio MCP 客户端（单例使用 mcp）：懒启动子进程，请求串行化"""

    def __init__(self):
        self._proc = None
        self._lock = threading.Lock()
        self._id = 0

    # ---------- 通道管理 ----------

    def _ensure(self):
        """确保子进程存活并完成 initialize 握手（调用方须持有锁）"""
        if self._proc is not None and self._proc.poll() is None:
            return
        self._proc = subprocess.Popen(
            [sys.executable, "-m", "app.services.mcp_server"],
            cwd=BASE_DIR,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        result = self._request({
            "jsonrpc": "2.0", "id": self._next_id(), "method": "initialize",
            "params": {"protocolVersion": PROTOCOL_VERSION, "capabilities": {},
                       "clientInfo": CLIENT_INFO},
        })
        if "serverInfo" not in result:
            raise McpError("MCP 握手失败")
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def _send(self, msg: dict):
        self._proc.stdin.write(json.dumps(msg, ensure_ascii=False) + "\n")
        self._proc.stdin.flush()

    def _read(self) -> dict:
        line = self._proc.stdout.readline()
        if not line:
            raise McpError("MCP 服务端连接已关闭")
        return json.loads(line)

    def _request(self, msg: dict) -> dict:
        """发送请求并等待对应响应（调用方须持有锁）"""
        self._send(msg)
        mid = msg.get("id")
        while True:
            resp = self._read()
            if resp.get("id") != mid:
                continue  # 跳过乱序/通知消息
            if "error" in resp:
                raise McpError(resp["error"].get("message", "MCP 调用失败"))
            return resp.get("result", {})

    def request(self, method: str, params: dict = None) -> dict:
        with self._lock:
            self._ensure()
            return self._request({
                "jsonrpc": "2.0", "id": self._next_id(), "method": method,
                "params": params or {},
            })

    def close(self):
        with self._lock:
            if self._proc is not None and self._proc.poll() is None:
                try:
                    self._proc.stdin.close()
                except OSError:
                    pass
            self._proc = None

    # ---------- MCP 能力 ----------

    def list_tools(self) -> list:
        return self.request("tools/list").get("tools", [])

    def call_tool(self, name: str, arguments: dict) -> str:
        """调用 MCP 工具，返回文本结果；isError 时抛 McpError"""
        result = self.request("tools/call", {"name": name, "arguments": arguments})
        text = "\n".join(
            c.get("text", "") for c in (result.get("content") or []) if c.get("type") == "text"
        )
        if result.get("isError"):
            raise McpError(text or "MCP 工具执行失败")
        return text


mcp = McpClient()  # 模块级单例


def call_tool(name: str, arguments: dict) -> str:
    return mcp.call_tool(name, arguments)


def list_tools() -> list:
    return mcp.list_tools()
