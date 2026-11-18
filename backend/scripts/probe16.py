# -*- coding: utf-8 -*-
"""第十六轮：带签名的淘宝历史链接查询 + 普通淘宝链接对照"""
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
DEAL_URL = "https://cu.manmanbuy.com/discuxiao_592883944.aspx"


def capture_query(page, url, wait_sec=25):
    """打开历史价格页并触发查询，捕获 api.ashx 响应"""
    api = []

    def on_resp(r):
        if "tool.manmanbuy.com/api.ashx" in r.url:
            try:
                api.append((r.url, r.text()))
            except Exception:
                pass

    page.on("response", on_resp)
    page.goto(url, timeout=40000, wait_until="domcontentloaded")
    for i in range(wait_sec):
        page.wait_for_timeout(1000)
        # 没有 api 请求且输入框可见时，点查询按钮
        if not api:
            try:
                if page.locator("#historykey").is_visible() and page.locator("iframe").count() == 0:
                    page.fill("#historykey", "")  # 清空以触发提交? 不，直接点
                    page.click("#searchHistory")
            except Exception:
                pass
        if api and '"data":{' in api[-1][1]:
            break
    page.remove_listener("response", on_resp)
    return api


def main():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=UA, locale="zh-CN", viewport={"width": 1366, "height": 900},
            storage_state=STORAGE if os.path.exists(STORAGE) else None,
        )
        page = ctx.new_page()

        # 1. 从爆料页提取签名历史链接
        print("== 1. 提取签名链接 ==")
        page.goto(DEAL_URL, timeout=35000, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        links = page.eval_on_selector_all(
            "a[href]",
            "els => els.map(e=>e.href)",
        )
        signed = [h for h in links if "HistoryLowest.aspx" in h and "st=" in h]
        print("签名链接数:", len(signed))
        if not signed:
            print("没有签名链接，退出")
            browser.close()
            return
        hist_url = signed[0]
        print("使用:", hist_url[:200])

        # 2. 打开签名历史链接
        print("== 2. 签名链接查询 ==")
        api = capture_query(page, hist_url, 25)
        print("api.ashx 响应:", len(api))
        for u, b in api[:3]:
            print("  ", b[:2500])
        page.screenshot(path=os.path.join(BASE, "shot_p16.png"))
        # 页面文本
        try:
            t = page.locator("body").inner_text()
            i = t.find("历史价格")
            print("页面片段:", t[max(0, i - 100): i + 900])
        except Exception:
            pass

        # 3. 普通淘宝链接对照
        print("== 3. 普通淘宝链接 ==")
        page.goto("https://tool.manmanbuy.com/HistoryLowest.aspx", timeout=35000, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        # 从签名链接里还原普通淘宝链接
        m = re.search(r"url=([^&]+)", hist_url)
        plain_tb = m.group(1) if m else ""
        from urllib.parse import unquote
        plain_tb = unquote(plain_tb)
        print("还原淘宝链接:", plain_tb[:150])
        api2 = capture_query(
            page,
            "https://tool.manmanbuy.com/HistoryLowest.aspx?url=" + plain_tb,
            20,
        )
        print("api.ashx 响应:", len(api2))
        for u, b in api2[:2]:
            print("  ", b[:1500])

        browser.close()


if __name__ == "__main__":
    main()
    print("PROBE16_DONE")
