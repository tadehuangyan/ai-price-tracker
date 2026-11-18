# -*- coding: utf-8 -*-
"""第十五轮：
1. 京东授权弹窗点“已完成授权”后再查
2. 换非京东链接（淘宝/当当等）查历史
3. 从爆料页提取原始平台链接
"""
import json
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORAGE = os.path.join(BASE, "storage", "manmanbuy_state.json")
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", os.path.join(BASE, "ms-playwright"))

# 浏览器 UA 伪装，与登录时保持一致避免会话校验差异
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def run_query(page, target_url, wait_sec=25):
    """在历史价格页发起一次查询，期间处理授权/登录弹窗，收集 api 响应与 XHR"""
    api = []
    xhrs = []

    def on_resp(r):
        if r.request.resource_type in ("xhr", "fetch") and "manmanbuy" in r.url:
            try:
                api.append((r.url, r.text()[:3000]))
            except Exception:
                pass

    def on_req(r):
        if r.resource_type in ("xhr", "fetch") and "manmanbuy" in r.url:
            xhrs.append(r.url)

    page.on("response", on_resp)
    page.on("request", on_req)
    try:
        page.fill("#historykey", target_url)
        page.click("#searchHistory")
    except Exception as e:
        print("  触发失败:", e)

    for i in range(wait_sec):
        page.wait_for_timeout(1000)
        # 点“已完成授权”按钮（京东授权弹窗）
        try:
            btn = page.get_by_text("已完成授权", exact=False)
            if btn.count() and btn.first.is_visible():
                btn.first.click(timeout=1500)
                print(f"  [{i}s] 点击已完成授权")
        except Exception:
            pass
        # 关登录弹窗
        if i % 8 == 7:
            try:
                for f in page.frames:
                    if "login" in f.url:
                        f.locator("[class*=close], .close").first.click(timeout=1200)
                        print(f"  [{i}s] 关闭登录弹窗")
            except Exception:
                pass
        # 有历史数据就提前结束
        if any("api.ashx" in u and "data" in b and '"data":null' not in b for u, b in api):
            break

    page.remove_listener("response", on_resp)
    page.remove_listener("request", on_req)
    return api, xhrs


def main():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=UA, locale="zh-CN", viewport={"width": 1366, "height": 900},
            storage_state=STORAGE if os.path.exists(STORAGE) else None,
        )
        page = ctx.new_page()

        # ===== 1. 爆料页提取原始链接 =====
        print("== 1. 爆料页原始链接 ==")
        page.goto("https://cu.manmanbuy.com/discuxiao_592883944.aspx", timeout=35000, wait_until="domcontentloaded")
        page.wait_for_timeout(3500)
        print("title:", page.title()[:60])
        links = page.eval_on_selector_all(
            "a[href]",
            "els => els.map(e=>({t:(e.innerText||'').replace(/\\s+/g,' ').slice(0,30), h:e.href}))",
        )
        plat = [l for l in links if re.search(r"item\.taobao|detail\.tmall|item\.jd|pinduoduo|dangdang|suning|vip\.com", l["h"])]
        print("平台链接:", json.dumps(plat[:8], ensure_ascii=False, indent=1))
        go = [l for l in links if re.search(r"(go|jump|redirect|url|link)=", l["h"], re.I) and "manmanbuy" in l["h"]]
        print("站内跳转:", json.dumps(go[:8], ensure_ascii=False, indent=1))
        # 按钮文本
        btns = page.eval_on_selector_all(
            "a, button, input[type=button]",
            "els => els.map(e=>(e.innerText||e.value||'').trim()).filter(t=>t && t.length<15)",
        )
        print("按钮:", json.dumps(list(set(btns))[:30], ensure_ascii=False))

        # ===== 2. 京东链接 + 点授权按钮 =====
        print("== 2. 京东查询(点已完成授权) ==")
        page.goto("https://tool.manmanbuy.com/HistoryLowest.aspx", timeout=35000, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        api, xhrs = run_query(page, "https://item.jd.com/100012043978.html", 20)
        print("  api响应:")
        for u, b in api:
            if "api.ashx" in u:
                print("   ", u[:150], "->", b[:1000])
        if not api:
            print("  无 api 响应; xhr:", json.dumps(xhrs[:10], ensure_ascii=False))

        # ===== 3. 非京东链接（当当商品）=====
        print("== 3. 当当链接查询 ==")
        page.goto("https://tool.manmanbuy.com/HistoryLowest.aspx", timeout=35000, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        dangdang_url = "product.dangdang.com/29808571.html"
        api2, xhrs2 = run_query(page, dangdang_url, 20)
        print("  api响应:")
        for u, b in api2:
            if "api.ashx" in u:
                print("   ", u[:150], "->", b[:1200])
        if not api2:
            print("  无 api 响应; xhr:", json.dumps(xhrs2[:10], ensure_ascii=False))

        page.screenshot(path=os.path.join(BASE, "shot_p15.png"))
        browser.close()


if __name__ == "__main__":
    main()
    print("PROBE15_DONE")
