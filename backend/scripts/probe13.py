# -*- coding: utf-8 -*-
"""用保存的登录态验证历史价格查询，并解析数据结构"""
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORAGE = os.path.join(BASE, "storage", "manmanbuy_state.json")
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", os.path.join(BASE, "ms-playwright"))

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def main():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=UA, locale="zh-CN",
            viewport={"width": 1366, "height": 900},
            storage_state=STORAGE if os.path.exists(STORAGE) else None,
        )
        page = ctx.new_page()

        api_resps = []
        page.on(
            "response",
            lambda r: api_resps.append(r)
            if "tool.manmanbuy.com/api.ashx" in r.url
            else None,
        )

        # 打印关键 cookie
        names = [c["name"] for c in ctx.cookies() if "manmanbuy" in c["domain"]]
        print("manmanbuy cookies:", names)

        page.goto("https://tool.manmanbuy.com/HistoryLowest.aspx", timeout=40000, wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
        # 页头是否显示登录
        head = page.locator("body").inner_text()[:200]
        print("页头:", head.replace("\n", " | "))

        page.fill("#historykey", "https://item.jd.com/100012043978.html")
        page.click("#searchHistory")

        for i in range(25):
            page.wait_for_timeout(1000)
            if api_resps:
                break
            # 若 5 秒后仍有登录弹窗，记录
            if i == 5 and page.locator("iframe").count():
                print("仍有登录弹窗")

        print("api.ashx 响应数:", len(api_resps))
        for r in api_resps[:3]:
            try:
                body = r.text()
            except Exception:
                body = "<read error>"
            print("URL:", r.url[:200])
            print("BODY:", body[:3000])
            print()

        page.screenshot(path=os.path.join(BASE, "shot_verify.png"))
        try:
            text = page.locator("body").inner_text()
            i = text.find("历史价格")
            print("页面片段:", text[max(0, i - 200): i + 1200])
        except Exception:
            pass
        browser.close()


if __name__ == "__main__":
    main()
    print("PROBE13_DONE")
