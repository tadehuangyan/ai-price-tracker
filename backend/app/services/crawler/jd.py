# -*- coding: utf-8 -*-
"""京东商品页采集：优先走 p.3.cn 价格接口，失败则解析页面价格节点"""
import re

import httpx

from .core import HEADERS_UA, launch_page, close_all


def _sku_from_url(url: str) -> str:
    """从京东链接提取 SKU ID（item.jd.com/<sku> 或 ?sku= 参数），取不到返回空串"""
    m = re.search(r"item\.jd\.com/(\d+)", url) or re.search(r"[?&]sku=(\d+)", url)
    return m.group(1) if m else ""


def _price_via_api(sku: str):
    """调用京东 p.3.cn 价格接口获取当前价（比解析页面更快更稳），失败返回 None"""
    r = httpx.get(
        "https://p.3.cn/prices/mgets",
        params={"type": 1, "skuIds": f"J_{sku}"},
        headers={"User-Agent": HEADERS_UA, "Referer": f"https://item.jd.com/{sku}.html"},
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    if isinstance(data, list) and data and "p" in data[0]:
        return float(data[0]["p"])  # "p" 字段为京东价
    return None


def fetch(url: str) -> dict:
    """京东商品页采集 -> {platform, title, price, image_url}；解析不到价格返回 None

    价格优先走 p.3.cn 接口，接口失败/无 SKU 时解析页面价格节点兜底。
    """
    sku = _sku_from_url(url)
    price = None
    if sku:
        try:
            price = _price_via_api(sku)
        except Exception:
            price = None  # 接口失败降级到页面解析

    p, browser, page = launch_page()
    try:
        page.goto(url, timeout=25000, wait_until="domcontentloaded")
        page.wait_for_timeout(2500)  # 等待价格节点渲染完成
        title = ""
        try:
            title = page.locator("div.sku-name, .itemInfo-wrap .sku-name").first.inner_text().strip()
        except Exception:
            title = (page.title() or "").replace("-京东", "").strip()  # 兜底取页面标题
        image = ""
        try:
            image = page.locator("#spec-img, .preview img").first.get_attribute("src") or ""
        except Exception:
            pass
        if price is None:
            # 解析页面价格节点
            try:
                txt = page.locator(".p-price .price, .p-price i, .summary-price .price").first.inner_text()
                m = re.search(r"(\d+(?:\.\d+)?)", txt)
                if m:
                    price = float(m.group(1))
            except Exception:
                price = None
        if price is None:
            # 页面源码兜底
            html = page.content()
            m = re.search(r'"price"\s*:\s*"?(\d+(?:\.\d+)?)"?', html)
            if m:
                price = float(m.group(1))
        if price is None:
            return None
        return {"platform": "jd", "title": title, "price": price, "image_url": image}
    finally:
        close_all(p, browser, page)
