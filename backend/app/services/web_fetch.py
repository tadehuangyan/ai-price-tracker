# -*- coding: utf-8 -*-
"""网页获取工具：抓取网页正文 / 网页搜索（供 MCP 服务端与 Agent 使用）

- fetch_page_text(url)：抓取网页并提取标题与正文文本
- search_snippets(query)：网页搜索，返回标题/链接/摘要列表
- 统一 UA 与超时、限制正文长度；仅允许 http/https 并拦截内网地址（基础 SSRF 防护）
"""
import html as html_module
import ipaddress
import re
from urllib.parse import quote, urlparse

import httpx

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
FETCH_TIMEOUT = 15  # 秒
MAX_CHARS = 3000  # 正文最大返回长度


def validate_url(url: str) -> str:
    """校验 URL：仅 http/https，拦截 localhost 与内网 IP（基础 SSRF 防护）"""
    url = (url or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("仅支持 http/https 链接")
    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError("链接缺少主机名")
    if host in ("localhost", "localhost.localdomain") or host.endswith(".local"):
        raise ValueError("不允许访问内网地址")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return url  # 主机名为公网域名（非 IP 字面量），交由 DNS 解析
    # IP 字面量：私网/回环/链路本地地址一律拒绝（防 SSRF 探内网）
    if ip.is_private or ip.is_loopback or ip.is_link_local:
        raise ValueError("不允许访问内网地址")
    return url


def _clean(fragment: str) -> str:
    """去掉 HTML 标签并反转义实体，得到纯文本片段"""
    return html_module.unescape(re.sub(r"<[^>]+>", " ", fragment or "")).strip()


def html_to_text(page: str) -> tuple:
    """HTML -> (title, 正文文本)：去脚本/样式/标签，保留段落换行"""
    m = re.search(r"<title[^>]*>(.*?)</title>", page, re.S | re.I)
    title = _clean(m.group(1)) if m else ""
    # 先剔除脚本/样式/注释等非正文内容，避免把代码当正文
    body = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", page, flags=re.S | re.I)
    body = re.sub(r"<!--.*?-->", " ", body, flags=re.S)
    # 块级结束标签转为换行，保留段落结构
    body = re.sub(r"<br\s*/?>|</p>|</div>|</li>|</h[1-6]>|</tr>", "\n", body, flags=re.I)
    body = re.sub(r"<[^>]+>", " ", body)  # 其余标签一律去掉
    body = html_module.unescape(body)
    body = re.sub(r"[ \t\u3000]+", " ", body)  # 压缩半角/全角空白
    body = re.sub(r"\n\s*\n+", "\n", body)  # 合并连续空行
    return title, body.strip()[:MAX_CHARS]


def fetch_page_text(url: str) -> dict:
    """抓取网页 -> {title, text, url}"""
    url = validate_url(url)
    resp = httpx.get(url, headers={"User-Agent": UA}, timeout=FETCH_TIMEOUT, follow_redirects=True)
    resp.raise_for_status()
    title, text = html_to_text(resp.text)
    return {"title": title or url, "text": text or "（网页无可提取正文）", "url": str(resp.url)}


def search_snippets(query: str, limit: int = 5) -> list:
    """网页搜索（必应）-> [{title, url, snippet}]，无结果返回空列表"""
    query = (query or "").strip()
    if not query:
        raise ValueError("缺少搜索关键词")
    url = f"https://www.bing.com/search?q={quote(query)}&setlang=zh-CN"
    resp = httpx.get(url, headers={"User-Agent": UA}, timeout=FETCH_TIMEOUT, follow_redirects=True)
    resp.raise_for_status()
    out = []
    # 解析必应自然结果块 li.b_algo，逐块提取标题链接与摘要
    for block in re.findall(r'<li class="b_algo".*?(?:</li>|$)', resp.text, re.S):
        hm = re.search(r'<h2[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)
        if not hm:
            continue
        link = hm.group(1)
        if not link.startswith("http"):
            continue  # 跳过站内跳转等非直链
        pm = re.search(r"<p[^>]*>(.*?)</p>", block, re.S)  # 摘要段落（可能不存在）
        out.append({
            "title": _clean(hm.group(2))[:80],
            "url": link,
            "snippet": _clean(pm.group(1))[:160] if pm else "",
        })
        if len(out) >= limit:
            break
    return out
