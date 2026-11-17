# -*- coding: utf-8 -*-
"""第九轮：关闭登录弹窗 -> 再触发查询 -> 抓 api 响应；并试 wap 端"""
import json
import os
import re

os.environ.setdefault(
    "PLAYWRIGHT_BROWSERS_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ms-playwright"),
)

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

        # ===== A. PC 端关弹窗重查 =====
        ctx = browser.new_context(user_agent=UA, locale="zh-CN", viewport={"width": 1366, "height": 900})
        ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = ctx.new_page()

        reqs, resps = [], []
        page.on(
            "request",
            lambda r: reqs.append({"m": r.method, "u": r.url, "post": (r.post_data or "")[:400]})
            if ("manmanbuy" in r.url and r.resource_type in ("xhr", "fetch"))
            else None,
        )
        page.on(
            "response",
            lambda r: resps.append({"u": r.url, "b": r.text()[:4000]})
            if ("tool.manmanbuy" in r.url and "ashx" in r.url)
            else None,
        )

        print("== A. PC 关弹窗 ==")
        page.goto("https://tool.manmanbuy.com/HistoryLowest.aspx", timeout=35000, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        page.fill("#historykey", "https://item.jd.com/100012043978.html")
        page.click("#searchHistory")
        page.wait_for_timeout(3500)

        # 关闭登录弹窗（iframe 外层关闭按钮）
        for sel in [".login-close", "[class*=close]", ".close", "img.close", ".lg-close"]:
            try:
                loc = page.locator(sel)
                if loc.count() and loc.first.is_visible():
                    loc.first.click(timeout=2000)
                    print("关闭弹窗:", sel)
                    break
            except Exception:
                continue
        else:
            # 点击遮罩区域 / ESC
            try:
                page.keyboard.press("Escape")
            except Exception:
                pass
            # iframe 内部关闭
            for f in page.frames:
                if "login" in f.url:
                    try:
                        f.locator("[class*=close], .close").first.click(timeout=2000)
                        print("iframe 内关闭")
                        break
                    except Exception:
                        pass
        page.wait_for_timeout(1500)

        # 关弹窗后再点一次查询
        reqs.clear()
        resps.clear()
        try:
            page.click("#searchHistory", timeout=3000)
            print("再次点击查询")
        except Exception as e:
            print("再次点击失败:", e)

        for _ in range(15):
            page.wait_for_timeout(1000)
            if resps:
                page.wait_for_timeout(2000)
                break
        print("tool 响应数:", len(resps))
        for r in resps[:5]:
            print(" ", r["u"][:160])
            print("   ", r["b"][:2500])
        print("XHR 汇总:")
        for r in reqs[:20]:
            print("  ", r["m"], r["u"][:130], "|", r["post"][:150])

        try:
            page.screenshot(path=os.path.join(os.path.dirname(__file__), "..", "shot_history2.png"))
        except Exception:
            pass
        try:
            text = page.locator("body").inner_text()
            i = text.find("全网同款")
            print("结果区文本:\n", text[max(0, i - 600): i + 800])
        except Exception:
            pass
        ctx.close()

        # ===== B. wap 端 =====
        print("== B. wap m.manmanbuy.com ==")
        mctx = browser.new_context(user_agent=MOBILE_UA, locale="zh-CN", viewport={"width": 390, "height": 844})
        mp = mctx.new_page()
        mreqs = []
        mp.on(
            "request",
            lambda r: mreqs.append({"m": r.method, "u": r.url, "post": (r.post_data or "")[:300]})
            if ("manmanbuy" in r.url and r.resource_type in ("xhr", "fetch"))
            else None,
        )
        try:
            wap_url = "https://m.manmanbuy.com/HistoryLowest.aspx?url=https%3A//item.jd.com/100012043978.html"
            mp.goto(wap_url, timeout=35000, wait_until="domcontentloaded")
            mp.wait_for_timeout(6000)
            print("title:", mp.title())
            print("url:", mp.url[:150])
            txt = mp.locator("body").inner_text()
            print("文本:\n", txt[:1200])
            print("XHR:", json.dumps(mreqs[:15], ensure_ascii=False, indent=1))
        except Exception as e:
            print("wap 失败:", e)

        browser.close()


if __name__ == "__main__":
    main()
    print("PROBE9_DONE")
