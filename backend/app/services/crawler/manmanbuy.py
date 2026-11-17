# -*- coding: utf-8 -*-
"""慢慢买适配器：历史价格查询 + 商品搜索（需登录态 storage/manmanbuy_state.json）

工作原理：
1. 打开 tool.manmanbuy.com/HistoryLowest.aspx?url=<商品链接>
2. 页面自动调用 api.ashx (method=getHistoryTrend) 返回 JSON
3. 解析 datePrice 日线序列、当前价、历史最低价等

注意：京东商品受“京东授权”限制无法查询；淘宝/天猫等平台正常。
"""
import json
import logging
import os
import re
from datetime import datetime, timezone
from urllib.parse import quote, unquote

logger = logging.getLogger("spt.crawler.manmanbuy")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
STORAGE_PATH = os.path.join(BASE_DIR, "storage", "manmanbuy_state.json")

HEADERS_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

SITE_PLATFORM_MAP = {
    "淘宝天猫": "taobao",
    "淘宝": "taobao",
    "天猫": "taobao",
    "京东": "jd",
    "拼多多": "pdd",
    "唯品会": "vip",
    "苏宁易购": "suning",
    "苏宁": "suning",
    "当当": "dangdang",
    "国美": "gome",
    "亚马逊": "amazon",
}

# 慢慢买全网折扣一级分类（与慢慢买站内分类导航保持一致，code 为分类页 cf 代码）
MANMANBUY_CATEGORIES = [
    {"code": "cf3", "name": "手机数码"},
    {"code": "cf17", "name": "电脑办公"},
    {"code": "cf6", "name": "家用电器"},
    {"code": "cf16", "name": "居家生活"},
    {"code": "cf5", "name": "家具家装"},
    {"code": "cf12", "name": "服饰内衣"},
    {"code": "cf9", "name": "鞋包配饰"},
    {"code": "cf18", "name": "美妆个护"},
    {"code": "cf15", "name": "母婴玩具"},
    {"code": "cf19", "name": "运动户外"},
    {"code": "cf8", "name": "食品酒水"},
    {"code": "cf10", "name": "水果生鲜"},
    {"code": "cf1", "name": "医药保健"},
    {"code": "cf7", "name": "文化娱乐"},
    {"code": "cf2", "name": "绿植农宠"},
    {"code": "cf4", "name": "汽配摩托"},
    {"code": "cf13", "name": "活动优惠"},
    {"code": "cf11", "name": "卡券本地"},
    {"code": "cf14", "name": "其它"},
]


def _parse_date_price(raw: str):
    """解析 datePrice: "[ts,price,note],[ts,price,note]..." -> [(date, price)]"""
    points = []
    if not raw:
        return points
    for m in re.finditer(r"\[(\d{10,13})\s*,\s*([0-9.]+)\s*,\s*\"([^\"]*)\"\]", raw):
        ts, price, note = m.group(1), float(m.group(2)), m.group(3)
        if len(ts) == 13:
            ts = int(ts) // 1000
        d = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone().strftime("%Y-%m-%d")
        points.append((d, price))
    # 去重（同一天取最后一条）
    seen = {}
    for d, p in points:
        seen[d] = p
    return sorted(seen.items())


def query_history(product_url: str, timeout_ms: int = 30000) -> dict:
    """查询商品历史价格；返回 dict 或抛异常（每次启动独立浏览器）"""
    if not os.path.exists(STORAGE_PATH):
        raise RuntimeError("缺少慢慢买登录态，请先运行 scripts/login_manmanbuy.py 扫码登录")

    from .core import launch_page, close_all  # 复用启动逻辑

    p, browser, page = launch_page()
    try:
        _load_storage(browser)
        return query_history_with(page, product_url, timeout_ms)
    finally:
        close_all(p, browser, page)


def _load_storage(browser):
    try:
        browser.contexts[0].add_cookies(json.load(open(STORAGE_PATH, encoding="utf-8"))["cookies"])
    except Exception as e:
        logger.warning("载入登录态失败: %s", e)


def query_history_with(page, product_url: str, timeout_ms: int = 30000) -> dict:
    """在给定 page 上查询历史价格（复用浏览器时使用）"""
    api_result = {}

    def on_resp(resp):
        if "tool.manmanbuy.com/api.ashx" in resp.url:
            try:
                data = resp.json()
                if isinstance(data, dict) and data.get("code") == 0 and data.get("data"):
                    api_result.update(data["data"])
            except Exception:
                pass

    page.on("response", on_resp)
    try:
        target = "https://tool.manmanbuy.com/HistoryLowest.aspx?url=" + quote(product_url, safe="")
        page.goto(target, timeout=timeout_ms, wait_until="domcontentloaded")

        waited = 0
        while waited < timeout_ms:
            page.wait_for_timeout(1000)
            waited += 1000
            if api_result:
                break
            # 未出数据时主动点一次查询按钮（页面未自动查询的情况）
            if waited == 6000:
                try:
                    if page.locator("#historykey").is_visible() and page.locator("iframe").count() == 0:
                        page.fill("#historykey", product_url)
                        page.click("#searchHistory")
                except Exception:
                    pass
    finally:
        page.remove_listener("response", on_resp)

    if not api_result:
        raise RuntimeError("慢慢买未返回历史价格数据（商品可能未收录或平台受限）")

    history = _parse_date_price(api_result.get("datePrice") or "")
    site = api_result.get("siteName") or ""
    title = (api_result.get("spName") or "").strip()
    current = api_result.get("currentPrice") or 0
    if not current and history:
        current = history[-1][1]
    return {
        "platform": SITE_PLATFORM_MAP.get(site, (site or "manmanbuy").lower()),
        "site_name": site,
        "title": title,
        "price": round(float(current), 2),
        "image_url": api_result.get("spPic") or "",
        "history_min": api_result.get("lowerPrice"),
        "history_min_date": (api_result.get("lowerDate") or "")[:10],
        "avg_price_60": api_result.get("avgPrice60"),
        "product_url": api_result.get("spUrl") or product_url,
        "history": history,
    }


def discover_products(keyword: str, limit: int = 12) -> list:
    """慢慢买 c=search 比价搜索：发现商品列表（需登录态才能看到商品卡片）

    返回 [{title, price, platform, url, image}]，url 为历史价格查询可用的原始商品链接。
    """
    from .core import launch_page, close_all

    p, browser, page = launch_page()
    _load_storage(browser)  # 未登录时搜索结果不展示商品链接
    try:
        url = (
            "https://s.manmanbuy.com/pc/search/result?keyword="
            + quote(keyword)
            + "&c=search"
        )
        page.goto(url, timeout=35000, wait_until="domcontentloaded")
        page.wait_for_timeout(4000)
        # 每张卡片取：标题、价格、平台、历史链接、图片
        cards = page.eval_on_selector_all(
            "a[href*='HistoryLowest']",
            """els => els.map(e => {
                const box = e.closest('li, div[class*=box]') || e.parentElement;
                const img = box ? box.querySelector('img') : null;
                const text = box ? box.innerText.replace(/\\s+/g, ' ').slice(0, 400) : '';
                const m = text.match(/¥\\s*([0-9]+(?:\\.[0-9]+)?)/);
                let plat = '';
                const pm = text.match(/(京东|淘宝|天猫|拼多多|唯品会|苏宁|当当|国美|亚马逊)/);
                if (pm) plat = pm[1];
                return {
                    href: e.href,
                    text: text,
                    title: (text.split(/[|¥￥]/)[0] || '').trim(),
                    price: m ? parseFloat(m[1]) : null,
                    platform: plat,
                    image: img ? (img.dataset.src || img.src || '') : ''
                };
            })""",
        )
        seen, out = set(), []
        for c in cards:
            m = re.search(r"url=([^&]+)", c["href"])
            if not m:
                continue
            target = unquote(m.group(1))
            if target in seen:
                continue
            seen.add(target)
            if not c["title"] or len(c["title"]) < 5:
                continue
            out.append(
                {
                    "title": c["title"][:120],
                    "price": c["price"],
                    "platform": c["platform"] or "",
                    "url": target,
                    "image": c["image"],
                    "keyword": keyword,
                }
            )
            if len(out) >= limit:
                break
        return out
    finally:
        close_all(p, browser, page)


def browse_category(cf_code: str = "", limit: int = 24) -> list:
    """慢慢买全网折扣分类页：实时抓取该一级分类的最新商品爆料

    cf_code 为空表示「全部分类」；返回 [{title, price, platform, url, image, time, tag, kind:'deal'}]，
    url 为爆料页链接（需 extract_deal / live_product 解析出原始商品链接）。
    """
    from .core import launch_page, close_all

    p, browser, page = launch_page()
    _load_storage(browser)  # 未登录时分类页会弹验证码拦截
    try:
        url = f"https://zhekou.manmanbuy.com/search/{cf_code or '0'}/0/0/0/1"
        page.goto(url, timeout=40000, wait_until="domcontentloaded")
        page.wait_for_timeout(4000)
        cards = page.eval_on_selector_all(
            "li.item",
            """els => els.map(e => {
                const a = e.querySelector('a.itemTitle') || e.querySelector('.cover a');
                const sub = e.querySelector('a.itemSubTitle');
                const img = e.querySelector('.cover img');
                const mall = e.querySelector('.mall');
                const time = e.querySelector('.time');
                const tag = e.querySelector('.tag-box span');
                const m = (sub ? sub.innerText : '').match(/([0-9]+(?:\\.[0-9]+)?)/);
                return {
                    title: (a ? (a.innerText || a.getAttribute('title') || '') : '').replace(/\\s+/g, ' ').trim(),
                    url: a ? a.href : '',
                    price: m ? parseFloat(m[1]) : null,
                    image: img ? (img.dataset.src || img.src || '') : '',
                    platform: mall ? mall.innerText.trim() : '',
                    time: time ? time.innerText.trim() : '',
                    tag: tag ? tag.innerText.trim() : ''
                };
            })""",
        )
        out = []
        for c in cards:
            if not c["title"] or not c["url"]:
                continue
            c["kind"] = "deal"
            out.append(c)
            if len(out) >= limit:
                break
        return out
    finally:
        close_all(p, browser, page)


def search_deals(keyword: str, limit: int = 10) -> list:
    """慢慢买折扣搜索：返回爆料列表 [{title, deal_price, url}]"""
    from .core import launch_page, close_all

    p, browser, page = launch_page()
    try:
        url = (
            "https://s.manmanbuy.com/pc/search/result?keyword="
            + quote(keyword)
            + "&c=discount"
        )
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        cards = page.eval_on_selector_all(
            "a[href*='discuxiao']",
            """els => els.map(e => {
                const box = e.closest('li, div');
                return {
                    href: e.href,
                    text: (box ? box.innerText : e.innerText).replace(/\\s+/g, ' ').slice(0, 300)
                };
            })""",
        )
        seen, out = set(), []
        for c in cards:
            if c["href"] in seen:
                continue
            seen.add(c["href"])
            m = re.search(r"(\d+(?:\.\d+)?)\s*元", c["text"])
            out.append(
                {
                    "url": c["href"],
                    "keyword": keyword,
                    "deal_price": float(m.group(1)) if m else None,
                    "text": c["text"],
                }
            )
            if len(out) >= limit:
                break
        return out
    finally:
        close_all(p, browser, page)


def extract_deal(deal_url: str) -> dict:
    """爆料页 -> 原始商品链接 + 标题 + 平台链接"""
    from .core import launch_page, close_all

    p, browser, page = launch_page()
    try:
        return extract_deal_with(page, deal_url)
    finally:
        close_all(p, browser, page)


def extract_deal_with(page, deal_url: str) -> dict:
    """在给定 page 上解析爆料页（复用浏览器时使用）"""
    from urllib.parse import unquote

    page.goto(deal_url, timeout=30000, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    title = ""
    try:
        title = page.locator("h1").first.inner_text().strip()
    except Exception:
        title = (page.title() or "").split("_")[0].strip()
    hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
    target = ""
    signed = [h for h in hrefs if "HistoryLowest.aspx" in h and "st=" in h]
    if signed:
        m = re.search(r"url=([^&]+)", signed[0])
        if m:
            target = unquote(m.group(1))
    if not target:
        m = re.search(r"url=([^&]+)", " ".join(hrefs))
        if m:
            target = unquote(m.group(1))
    # 爆料价
    text = page.locator("body").inner_text()[:2000]
    pm = re.search(r"到手价[：:]\s*￥?\s*([0-9.]+)", text)
    price = float(pm.group(1)) if pm else None
    return {"title": title, "product_url": target, "deal_price": price, "deal_url": deal_url}


def live_product(url: str, timeout_ms: int = 30000) -> dict:
    """实时商品详情（不写库）：任意商品/爆料链接 -> 慢慢买历史价格全量数据

    爆料链接（cu.manmanbuy.com/discuxiao_*）先解析出原始商品链接；一次浏览器会话完成。
    """
    if not os.path.exists(STORAGE_PATH):
        raise RuntimeError("缺少慢慢买登录态，请先运行 scripts/login_manmanbuy.py 扫码登录")

    from .core import launch_page, close_all

    p, browser, page = launch_page()
    try:
        _load_storage(browser)
        target = url
        deal_url = ""
        if "manmanbuy.com/discuxiao" in url:
            deal_url = url
            info = extract_deal_with(page, url)
            target = (info.get("product_url") or "").strip()
            if not target:
                raise RuntimeError("未能从爆料页解析出原始商品链接")
        data = query_history_with(page, target, timeout_ms)
        data["deal_url"] = deal_url
        return data
    finally:
        close_all(p, browser, page)


def fetch(url: str) -> dict:
    """统一入口：任何商品链接 -> 慢慢买历史价格查询"""
    return query_history(url)
