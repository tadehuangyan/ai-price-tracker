# -*- coding: utf-8 -*-
"""真实数据初始化：慢慢买比价搜索发现商品 -> 查询历史价格 -> 写入 MySQL

运行: python scripts/seed_data.py
"""
import os
import re
import sys
import time
from datetime import datetime
from urllib.parse import quote, unquote

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", os.path.join(BASE, "ms-playwright"))

# (搜索关键词, 分类, 每词取几个)
KEYWORDS = [
    ("手机", "手机", 4),
    ("机械键盘", "电脑外设", 4),
    ("蓝牙耳机", "数码配件", 4),
    ("扫地机器人", "家用电器", 3),
    ("路由器", "网络设备", 3),
    ("显示器", "电脑外设", 3),
    ("充电宝", "数码配件", 3),
    ("吹风机", "家用电器", 3),
    ("内存条", "电脑配件", 4),
    ("DDR5 台式机内存", "电脑配件", 3),
]

# 浏览器 UA 伪装，避免被站点按默认 UA 识别为爬虫
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def collect_search_links(page, keyword: str, limit: int) -> list:
    """c=search 结果页 -> [{product_url, title, price, platform_text}]"""
    url = "https://s.manmanbuy.com/pc/search/result?keyword=" + quote(keyword) + "&c=search"
    page.goto(url, timeout=35000, wait_until="domcontentloaded")
    page.wait_for_timeout(4000)
    cards = page.eval_on_selector_all(
        "a[href*='HistoryLowest']",
        """els => els.map(e => {
            const box = e.closest('li, div[class*=box], div[class*=Item]');
            return {href: e.href, text: box ? box.innerText.replace(/\\s+/g, ' ').slice(0, 300) : ''};
        })""",
    )
    out, seen = [], set()
    for c in cards:
        m = re.search(r"url=([^&]+)", c["href"])
        if not m:
            continue
        target = unquote(m.group(1))
        if target in seen:
            continue
        seen.add(target)
        # 标题：卡片文本第一段
        title = c["text"].split("|")[0].strip() if c["text"] else ""
        title = re.sub(r"\s+", " ", title)[:120]
        pm = re.search(r"¥\s*(\d+(?:\.\d+)?)", c["text"])
        out.append(
            {
                "product_url": target,
                "title": title,
                "search_price": float(pm.group(1)) if pm else None,
                "keyword": keyword,
            }
        )
        if len(out) >= limit:
            break
    return out


def main():
    from playwright.sync_api import sync_playwright

    from app.database import SessionLocal
    from app.models import Listing, PriceSnapshot, Product, SystemLog
    from app.services.crawler.manmanbuy import STORAGE_PATH, query_history_with

    # 关键词过滤：python scripts/seed_data.py 内存  -> 只跑含"内存"的关键词
    keywords = KEYWORDS
    if len(sys.argv) > 1:
        kw_filter = sys.argv[1]
        keywords = [k for k in KEYWORDS if kw_filter in k[0]]
        if not keywords:
            print(f"没有匹配的关键词: {kw_filter}")
            sys.exit(1)
        print(f"按关键词过滤: {[k[0] for k in keywords]}")

    if not os.path.exists(STORAGE_PATH):
        print("缺少慢慢买登录态，请先运行 login_manmanbuy.py")
        sys.exit(1)

    with open(STORAGE_PATH, encoding="utf-8") as f:
        storage_cookies = __import__("json").load(f)["cookies"]

    db = SessionLocal()
    total_products = total_points = 0
    failed = []

    with sync_playwright() as p:
        # 关闭自动化特征并使用中文环境启动浏览器，降低被风控概率
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(user_agent=UA, locale="zh-CN", viewport={"width": 1366, "height": 900})
        ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        # 注入慢慢买登录态
        ctx.add_cookies(storage_cookies)
        page = ctx.new_page()

        # 1) 收集候选商品
        candidates = []
        seen_urls = set()
        for keyword, category, limit in keywords:
            try:
                items = collect_search_links(page, keyword, limit)
                for it in items:
                    if it["product_url"] in seen_urls:
                        continue
                    seen_urls.add(it["product_url"])
                    it["category"] = category
                    candidates.append(it)
                print(f"[搜索] {keyword}: {len(items)} 个候选")
            except Exception as e:
                print(f"[搜索] {keyword} 失败: {e}")
        print(f"候选商品总数: {len(candidates)}")

        # 2) 逐个查询历史价格并入库
        for i, c in enumerate(candidates, 1):
            # 每次查询前重载最新登录态（京东授权等状态可能已更新）
            try:
                with open(STORAGE_PATH, encoding="utf-8") as f:
                    page.context.add_cookies(__import__("json").load(f)["cookies"])
            except Exception:
                pass
            try:
                data = query_history_with(page, c["product_url"], timeout_ms=20000)
            except Exception as e:
                failed.append((c["product_url"], str(e)[:80]))
                print(f"[{i}/{len(candidates)}] 失败: {str(e)[:80]} | {c['title'][:30]}")
                continue

            title = data["title"] or c["title"]
            if not title:
                failed.append((c["product_url"], "无标题"))
                continue

            # 去重键：搜索结果里的原始链接（spUrl 每次查询会变，不能用）
            product = (
                db.query(Product)
                .join(Listing, Listing.product_id == Product.id)
                .filter(Listing.url == c["product_url"])
                .first()
            )
            if product is None:
                product = Product(name=title, category=c["category"], image_url=data["image_url"])
                db.add(product)
                db.flush()
                listing = Listing(
                    product_id=product.id,
                    platform=data["platform"] or "taobao",
                    platform_item_id=(data.get("product_url") or "")[-64:],
                    url=c["product_url"],
                    title=title,
                    current_price=data["price"],
                    last_crawled_at=datetime.now(),
                )
                db.add(listing)
                db.flush()
            else:
                listing = (
                    db.query(Listing)
                    .filter(Listing.product_id == product.id, Listing.url == c["product_url"])
                    .first()
                )
                listing.current_price = data["price"]
                listing.last_crawled_at = datetime.now()
                listing.title = title
                if data["image_url"]:
                    product.image_url = data["image_url"]

            # 历史日线 -> 价格快照
            existing = {
                s.strftime("%Y-%m-%d")
                for s in db.query(PriceSnapshot.captured_at)
                .filter(PriceSnapshot.listing_id == listing.id)
                .all()
            }
            points = 0
            for date_str, price in data["history"]:
                if date_str in existing:
                    continue
                snap_time = datetime.strptime(date_str + " 12:00:00", "%Y-%m-%d %H:%M:%S")
                db.add(PriceSnapshot(listing_id=listing.id, price=price, captured_at=snap_time))
                points += 1
            db.commit()
            total_products += 1
            total_points += points
            print(
                f"[{i}/{len(candidates)}] ✓ {title[:34]} | {data['site_name']} "
                f"当前 {data['price']} | 新增 {points} 天历史 | 累计 {total_points}"
            )
            time.sleep(1)  # 间隔防风控

        browser.close()

    db.add(SystemLog(module="seed", message=f"数据初始化：{total_products} 个商品，{total_points} 条价格快照，失败 {len(failed)}"))
    db.commit()
    db.close()
    print("=" * 50)
    print(f"完成：商品 {total_products}，价格快照 {total_points}，失败 {len(failed)}")
    for u, e in failed[:10]:
        print("  失败:", e, "|", u[:70])


if __name__ == "__main__":
    main()
