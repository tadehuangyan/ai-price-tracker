# -*- coding: utf-8 -*-
"""第七轮：
A. historyLowest 查询：记录全部请求，截图，等待更久
B. 首页比价搜索模式（data-bijia）
"""
import json
import os

os.environ.setdefault(
    "PLAYWRIGHT_BROWSERS_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ms-playwright"),
)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def main():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(user_agent=UA, locale="zh-CN", viewport={"width": 1366, "height": 900})
        ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = ctx.new_page()

        all_reqs = []

        def on_req(req):
            if "manmanbuy.com" in req.url and req.resource_type in ("xhr", "fetch"):
                try:
                    post = req.post_data or ""
                except Exception:
                    post = ""
                all_reqs.append({"method": req.method, "url": req.url, "post": post[:300]})

        page.on("request", on_req)

        # ===== A. historyLowest 查询 =====
        print("== A. historyLowest ==")
        page.goto("https://tool.manmanbuy.com/historyLowest.aspx", timeout=35000, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        page.fill("#historykey", "https://item.jd.com/100012043978.html")
        all_reqs.clear()
        page.click("#searchHistory")
        # 观察 25 秒
        for i in range(25):
            page.wait_for_timeout(1000)
        print("url:", page.url)
        print("XHR/Fetch:")
        for r in all_reqs:
            print("  ", r["method"], r["url"][:150], "| post:", r["post"][:200])
        try:
            page.screenshot(path=os.path.join(os.path.dirname(__file__), "..", "shot_history.png"), full_page=False)
            print("截图完成")
        except Exception as e:
            print("截图失败:", e)
        # 控制台错误
        # 结果区域 html 片段
        try:
            html = page.content()
            import re
            m = re.search(r"(查询中|暂无|历史价格走势|价格走势图)", html)
            print("结果关键词:", m.group(0) if m else "无")
            # 查看是否有 iframe
            frames = [f.url for f in page.frames]
            print("frames:", frames)
        except Exception as e:
            print(e)

        # ===== B. 首页比价搜索 =====
        print("== B. 首页比价搜索 ==")
        page.goto("https://www.manmanbuy.com/", timeout=35000, wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
        # 找比价 tab
        tabs = page.eval_on_selector_all(
            "[class*=tab], [class*=mode], [class*=switch], span, li, a",
            "els => els.map((e,i)=>({i, t:(e.innerText||'').trim().slice(0,15), cls:(e.className||'').toString().slice(0,40)}))"
            ".filter(x=>/比价|历史|折扣/.test(x.t)).slice(0,20)",
        )
        print("tabs:", json.dumps(tabs, ensure_ascii=False))
        # 尝试点击“比价”
        try:
            page.get_by_text("比价", exact=False).first.click(timeout=3000)
            page.wait_for_timeout(500)
            print("点击比价成功")
        except Exception as e:
            print("点比价:", e)
        try:
            inp = page.locator("#skey")
            inp.fill("机械键盘")
            page.wait_for_timeout(300)
            page.locator(".btnSearch").click()
            page.wait_for_timeout(4000)
            print("搜索后 url:", page.url)
            links = page.eval_on_selector_all(
                "a[href]",
                "els => els.map(e=>({t:(e.innerText||'').replace(/\\s+/g,' ').slice(0,40), h:e.href}))",
            )
            bb = [l for l in links if re.search(r"manmanbuy\.com/(BB|product|goods|detail)", l["h"])] if False else [l for l in links if "BB" in l["h"] or "/product" in l["h"]]
            for l in bb[:10]:
                print("  BB链接:", l)
            # 打印前 20 个结果链接
            res = [l for l in links if "manmanbuy.com" in l["h"]][:20]
            for l in res:
                print("  链接:", l)
        except Exception as e:
            print("搜索失败:", e)

        browser.close()


if __name__ == "__main__":
    import re

    main()
    print("PROBE7_DONE")
