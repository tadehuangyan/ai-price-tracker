# -*- coding: utf-8 -*-
"""调试：复现 seed 查询流程，打印 api.ashx 原始响应 + 页面状态"""
import json
import os
import re
import sys
from urllib.parse import quote, unquote

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", os.path.join(BASE, "ms-playwright"))

STORAGE = os.path.join(BASE, "storage", "manmanbuy_state.json")
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def main():
    from playwright.sync_api import sync_playwright

    with open(STORAGE, encoding="utf-8") as f:
        cookies = json.load(f)["cookies"]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(user_agent=UA, locale="zh-CN", viewport={"width": 1366, "height": 900})
        ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        ctx.add_cookies(cookies)
        page = ctx.new_page()

        # 1) 先像 seed 一样打开搜索页
        page.goto(
            "https://s.manmanbuy.com/pc/search/result?keyword=%E6%89%8B%E6%9C%BA&c=search",
            timeout=35000, wait_until="domcontentloaded",
        )
        page.wait_for_timeout(4000)
        links = page.eval_on_selector_all(
            "a[href*='HistoryLowest']",
            "els => els.map(e => e.href)",
        )
        print("搜索页 HistoryLowest 链接数:", len(links))
        if not links:
            print("无链接，退出")
            browser.close()
            return
        m = re.search(r"url=([^&]+)", links[0])
        target = unquote(m.group(1))
        print("目标商品链接:", target[:120])

        # 2) 查询（记录所有 api.ashx 响应）
        all_api = []

        def on_resp(r):
            if "tool.manmanbuy.com/api.ashx" in r.url:
                try:
                    all_api.append(r.text())
                except Exception:
                    all_api.append("<read fail>")

        page.on("response", on_resp)
        page.goto(
            "https://tool.manmanbuy.com/HistoryLowest.aspx?url=" + quote(target, safe=""),
            timeout=40000, wait_until="domcontentloaded",
        )
        for i in range(25):
            page.wait_for_timeout(1000)
            if all_api:
                break
            if i == 6:
                print("6s 无响应，检查弹窗/输入框")
                print("  iframe 数:", page.locator("iframe").count())
                print("  historykey 可见:", page.locator("#historykey").is_visible())
                for t in ["京东授权", "微信登录", "查询中"]:
                    try:
                        print(f"  含'{t}':", page.get_by_text(t).count())
                    except Exception:
                        pass

        print("api.ashx 响应数:", len(all_api))
        for b in all_api[:3]:
            print("  响应:", b[:600])
        page.screenshot(path=os.path.join(BASE, "shot_debug.png"))
        text = page.locator("body").inner_text()
        i = text.find("当前查询")
        print("页面片段:", text[max(0, i - 100): i + 500] if i >= 0 else text[:400])
        browser.close()


if __name__ == "__main__":
    main()
    print("DEBUG_DONE")
