# -*- coding: utf-8 -*-
"""爬虫可行性探测：慢慢买（历史价格）/ 京东（当前价）/ 淘宝（反爬探测）

运行: python scripts/probe_crawl.py
"""
import json
import sys

# 伪装浏览器请求头：UA 与中文语言，降低被目标站点直接拒绝的概率
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9",
}


def probe_httpx():
    """先用纯 HTTP 探测不需要浏览器的接口"""
    import httpx

    print("=" * 60)
    print("[1] 京东价格接口 p.3.cn")
    try:
        r = httpx.get(
            "https://p.3.cn/prices/mgets",
            params={"type": 1, "skuIds": "J_100012043978"},
            headers={**HEADERS, "Referer": "https://item.jd.com/"},
            timeout=10,
            verify=False,
        )
        print("  status:", r.status_code, "body:", r.text[:300])
    except Exception as e:
        print("  FAIL:", e)

    print("[2] 慢慢买 搜索接口")
    for url in [
        "https://s.manmanbuy.com/keywords.aspx?q=%E6%89%8B%E6%9C%BA",
        "https://s.manmanbuy.com/PC_%E6%89%8B%E6%9C%BA",
    ]:
        try:
            r = httpx.get(url, headers=HEADERS, timeout=10, follow_redirects=True, verify=False)
            print(f"  {url} -> {r.status_code}, len={len(r.text)}")
        except Exception as e:
            print(f"  {url} FAIL: {e}")


def probe_playwright():
    """浏览器探测：慢慢买历史价格页 / 京东商品页 / 淘宝商品页"""
    from playwright.sync_api import sync_playwright

    print("=" * 60)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(
            user_agent=HEADERS["User-Agent"],
            locale="zh-CN",
            viewport={"width": 1366, "height": 900},
        )
        page = ctx.new_page()

        # --- 慢慢买搜索 ---
        print("[3] 慢慢买搜索页")
        try:
            page.goto("https://s.manmanbuy.com/keywords.aspx?q=%E6%89%8B%E6%9C%BA", timeout=25000)
            page.wait_for_timeout(2500)
            print("  title:", page.title())
            links = page.eval_on_selector_all(
                "a",
                "els => els.map(e => ({t: (e.innerText||'').trim().slice(0,50), h: e.href}))"
                ".filter(x => x.t && /manmanbuy|history|BB\\d/i.test(x.h))",
            )
            for l in links[:8]:
                print("   link:", l)
        except Exception as e:
            print("  FAIL:", e)

        # --- 慢慢买历史价格（找一个 BB 详情页跟进） ---
        print("[4] 慢慢买历史价格页")
        try:
            # 常见历史价格页格式
            page.goto("https://tool.manmanbuy.com/history.aspx", timeout=25000)
            print("  title:", page.title(), "url:", page.url)
        except Exception as e:
            print("  FAIL:", e)

        # --- 京东商品页 ---
        print("[5] 京东商品页")
        try:
            page.goto("https://item.jd.com/100012043978.html", timeout=25000)
            page.wait_for_timeout(3000)
            print("  title:", page.title())
            html = page.content()
            print("  含'价格'文本:", "价格" in html, " 含'p-price':", "p-price" in html)
            # 尝试读取页面价格节点
            try:
                price_txt = page.eval_on_selector_all(
                    ".p-price .price, .p-price i",
                    "els => els.map(e => e.innerText).join('')",
                )
                print("  页面价格节点:", price_txt[:50])
            except Exception:
                pass
        except Exception as e:
            print("  FAIL:", e)

        # --- 淘宝商品页（探测反爬） ---
        print("[6] 淘宝商品页")
        try:
            page.goto("https://item.taobao.com/item.htm?id=699999999999", timeout=25000)
            page.wait_for_timeout(3000)
            print("  title:", page.title(), "url:", page.url[:100])
            html = page.content()
            print("  需要登录/验证:", ("login" in page.url) or ("登录" in page.title()) or ("验证码" in html))
        except Exception as e:
            print("  FAIL:", e)

        browser.close()


if __name__ == "__main__":
    import warnings

    warnings.filterwarnings("ignore")
    try:
        probe_httpx()
    except Exception as e:
        print("httpx probe error:", e)
    try:
        probe_playwright()
    except Exception as e:
        print("playwright probe error:", e)
        sys.exit(1)
