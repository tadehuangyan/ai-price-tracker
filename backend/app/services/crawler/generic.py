# -*- coding: utf-8 -*-
"""通用商品页采集：JSON-LD / meta / 常见价格节点多级兜底"""
import json
import re

from .core import launch_page, close_all


def _price_from_html(html: str):
    # 1) JSON-LD Product.offers.price
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
    # 2) meta itemprop / og
    m = re.search(r'<meta[^>]+itemprop="price"[^>]+content="(\d+(?:\.\d+)?)"', html)
    if m:
        return float(m.group(1)), ""
    m = re.search(r'"price"\s*:\s*"?(\d+(?:\.\d+)?)"?', html)
    if m:
        return float(m.group(1)), ""
    # 3) 页面可见价格文本
    m = re.search(r'[¥￥]\s*(\d+(?:\.\d{1,2})?)', html)
    if m:
        return float(m.group(1)), ""
    return None, ""


def fetch(url: str) -> dict:
    p, browser, page = launch_page()
    try:
        page.goto(url, timeout=25000, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        html = page.content()
        price, title = _price_from_html(html)
        if price is None:
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
            title = (page.title() or "").strip()[:100]
        if price is None:
            return None
        return {"platform": "web", "title": title, "price": price, "image_url": ""}
    finally:
        close_all(p, browser, page)
