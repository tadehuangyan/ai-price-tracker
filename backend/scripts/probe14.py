# -*- coding: utf-8 -*-
"""第十四轮：全量抓包分析查询流程"""
import json
import os
import time

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

        events = []

        def on_req(r):
            if r.resource_type in ("xhr", "fetch"):
                events.append(("REQ", r.method, r.url, (r.post_data or "")[:200]))

        def on_resp(r):
            if r.request.resource_type in ("xhr", "fetch"):
                try:
                    ct = r.headers.get("content-type", "")
                    body = r.text()[:1500] if "json" in ct or "text" in ct or "javascript" in ct else "<binary>"
                except Exception:
                    body = "<err>"
                events.append(("RESP", str(r.status), r.url, body))

        page.on("request", on_req)
        page.on("response", on_resp)

        # cookie 域
        for c in ctx.cookies():
            if "mmmuser" in c["name"] or "mmbuser" in c["name"]:
                print("登录 cookie:", c["name"], "domain=", c["domain"], "path=", c["path"])

        page.goto("https://tool.manmanbuy.com/HistoryLowest.aspx", timeout=40000, wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
        h1 = page.locator("body").inner_text()[:80]
        print("页头(初始):", h1.replace("\n", " | "))
        page.screenshot(path=os.path.join(BASE, "shot_p14_1.png"))

        page.fill("#historykey", "https://item.jd.com/100012043978.html")
        events.clear()
        page.click("#searchHistory")

        for i in range(30):
            page.wait_for_timeout(1000)
            # 每 5 秒关闭一次登录弹窗
            if i % 6 == 5:
                try:
                    for f in page.frames:
                        if "login" in f.url:
                            f.locator("[class*=close], .close").first.click(timeout=1500)
                            print(f"[{i}s] 关闭登录弹窗")
                except Exception:
                    pass

        h2 = page.locator("body").inner_text()[:80]
        print("页头(查询后):", h2.replace("\n", " | "))
        page.screenshot(path=os.path.join(BASE, "shot_p14_2.png"))

        print("=" * 40)
        for e in events:
            kind = e[0]
            if kind == "REQ":
                print("REQ ", e[1], e[2][:160], "|", e[3][:120])
            else:
                print("RESP", e[1], e[2][:160])
                if e[3] and e[3] != "<binary>" and len(e[3]) > 5:
                    print("     ", e[3][:800].replace("\n", " "))

        browser.close()


if __name__ == "__main__":
    main()
    print("PROBE14_DONE")
