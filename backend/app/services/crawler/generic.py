# -*- coding: utf-8 -*-
"""通用商品页采集：JSON-LD / meta / 常见价格节点多级兜底"""
import json
import re

from .core import launch_page, close_all


def _price_from_html(html: str):
    """从页面 HTML 多级兜底提取价格 -> (price, name)；全部失败返回 (None, "")

    优先级：JSON-LD 结构化数据 > meta 标签 > 页面内价格文本。
    """
    # 1) JSON-LD Product.offers.price（结构化数据最可靠，可能有多个 script 块）
    for m in re.finditer(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S):
        try:
            data = json.loads(m.group(1))
            items = data if isinstance(data, list) else [data]
            for it in items:
                if isinstance(it, dict) and it.get("@type") == "Product":
                    offer = it.get("offers") or {}
                    if isinstance(offer, list):
                        offer = offer[0] if offer else {}
                    p = offer.get("price") or offer.get("lowPrice")
                    if p:
                        return float(p), it.get("name", "")
        except Exception:
            continue
    # 2) meta itemprop / og（电商页常用的价格元信息），再兜底页面内嵌 "price" 字段
    m = re.search(r'<meta[^>]+itemprop="price"[^>]+content="(\d+(?:\.\d+)?)"', html)
    if m:
        return float(m.group(1)), ""
    m = re.search(r'"price"\s*:\s*"?(\d+(?:\.\d+)?)"?', html)
    if m:
        return float(m.group(1)), ""
    # 3) 页面可见价格文本（¥/￥ 开头的数字，最后的兜底手段）
    m = re.search(r'[¥￥]\s*(\d+(?:\.\d{1,2})?)', html)
    if m:
        return float(m.group(1)), ""
    return None, ""


def fetch(url: str) -> dict:
    """通用商品页采集入口 -> {platform, title, price, image_url}；解析不到价格返回 None"""
    p, browser, page = launch_page()
    try:
        page.goto(url, timeout=25000, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)  # 等待动态渲染出价格
        html = page.content()
        price, title = _price_from_html(html)
        if price is None:
            # HTML 静态解析失败时改从 DOM 价格节点读取（SPA 页面价格常异步注入）
            try:
                txt = page.locator(
                    "[itemprop='price'], .price, .realPrice, .p-price .price, .y-price"
                ).first.inner_text()
                m = re.search(r"(\d+(?:\.\d+)?)", txt)
                if m:
                    price = float(m.group(1))
            except Exception:
                pass
        if not title:
            title = (page.title() or "").strip()[:100]  # 兜底取页面标题
        if price is None:
            return None
        return {"platform": "web", "title": title, "price": price, "image_url": ""}
    finally:
        close_all(p, browser, page)
