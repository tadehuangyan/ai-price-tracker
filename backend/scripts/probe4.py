# -*- coding: utf-8 -*-
"""第四轮：慢慢买历史价格页 api.ashx 响应抓取 + 京东移动搜索"""
import json
import os
import re
import urllib.parse

os.environ.setdefault(
    "PLAYWRIGHT_BROWSERS_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ms-playwright"),
)

# 浏览器 UA 伪装：桌面端与移动端两套请求头，分别探测 PC/移动页面
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)


def main():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])

        # ===== 1. 慢慢买历史价格 =====
        ctx = browser.new_context(user_agent=UA, locale="zh-CN", viewport={"width": 1366, "height": 900})
        ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = ctx.new_page()

        api_responses = []

        def on_resp(resp):
            if "manmanbuy.com/api" in resp.url or "api.ashx" in resp.url:
                try:
                    api_responses.append({"url": resp.url, "body": resp.text()[:4000]})
                except Exception:
                    pass

        page.on("response", on_resp)

        target_url = "https://item.jd.com/100012043978.html"
        hist_page = "https://tool.manmanbuy.com/historyLowest.aspx?url=" + urllib.parse.quote(target_url, safe="")
        print("[慢慢买] 历史价格页:", hist_page)
        try:
            page.goto(hist_page, timeout=35000, wait_until="domcontentloaded")
            page.wait_for_timeout(6000)
            print("  title:", page.title())
            text = page.locator("body").inner_text()
            print("  页面文本:\n", text[:1200])
            print("  api 响应数:", len(api_responses))
            for r in api_responses[:5]:
                print("  API:", r["url"])
                print("   body:", r["body"][:1500])
        except Exception as e:
            print("  失败:", e)

        # ===== 2. 京东移动搜索 =====
        print("[京东] 移动搜索")
        mctx = browser.new_context(user_agent=MOBILE_UA, locale="zh-CN", viewport={"width": 390, "height": 844})
        mp = mctx.new_page()
        try:
            mp.goto("https://so.m.jd.com/ware/search.action?keyword=%E6%9C%BA%E6%A2%B0%E9%94%AE%E7%9B%98", timeout=30000, wait_until="domcontentloaded")
            mp.wait_for_timeout(4000)
            print("  title:", mp.title())
            print("  url:", mp.url[:120])
            links = mp.eval_on_selector_all(
                "a[href]",
                "els => els.map(e => ({t:(e.innerText||'').replace(/\\s+/g,' ').slice(0,50), h:e.href}))",
            )
            items = [l for l in links if "product" in l["h"] or "jd.com" in l["h"]]
            for l in items[:12]:
                print("   ", l)
            if not items:
                txt = mp.locator("body").inner_text()[:600]
                print("  文本:\n", txt)
        except Exception as e:
            print("  失败:", e)

        browser.close()


if __name__ == "__main__":
    main()
    print("PROBE4_DONE")
