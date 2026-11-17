# -*- coding: utf-8 -*-
"""慢慢买登录助手：打开可见浏览器窗口，用户微信扫码登录后保存登录态。

运行: python scripts/login_manmanbuy.py
登录态保存到: backend/storage/manmanbuy_state.json
"""
import json
import os
import sys
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORAGE = os.path.join(BASE, "storage", "manmanbuy_state.json")
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", os.path.join(BASE, "ms-playwright"))

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
JD_URL = "https://item.jd.com/100012043978.html"


def main():
    from playwright.sync_api import sync_playwright

    os.makedirs(os.path.dirname(STORAGE), exist_ok=True)
    state = STORAGE if os.path.exists(STORAGE) else None

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,  # 可见窗口，方便扫码
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            user_agent=UA,
            locale="zh-CN",
            viewport={"width": 1280, "height": 860},
            storage_state=state,
        )
        ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = ctx.new_page()

        api_resps = []
        page.on(
            "response",
            lambda r: api_resps.append(r)
            if ("tool.manmanbuy.com/api.ashx" in r.url)
            else None,
        )

        base_cookies = {c["name"] for c in ctx.cookies()}

        def has_new_login_cookie():
            names = {c["name"] for c in ctx.cookies()}
            new = names - base_cookies
            # 登录后通常会出现用户相关 cookie（排除统计类）
            ignore = {"Hm_lvt_", "Hm_lpvt", "_ga", "_gid", "_gat"}
            return any(not any(i in n for i in ignore) for n in new)

        def header_logged_in():
            try:
                t = page.locator("body").inner_text()[:500]
                return "请登录" not in t and "免费注册" not in t
            except Exception:
                return False

        page.goto("https://tool.manmanbuy.com/HistoryLowest.aspx", timeout=40000, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        page.fill("#historykey", JD_URL)
        page.click("#searchHistory")
        page.wait_for_timeout(3000)

        print("=" * 60)
        print("请在打开的浏览器窗口中完成登录（可能弹出微信扫码框）")
        print("登录成功后脚本会自动保存登录态并退出")
        print("=" * 60)
        sys.stdout.flush()

        deadline = time.time() + 300  # 5 分钟
        logged_in = False
        while time.time() < deadline:
            page.wait_for_timeout(2000)
            # 信号1：真正的历史数据接口 api.ashx 返回了 data
            for r in api_resps:
                try:
                    body = r.text()
                except Exception:
                    continue
                if '"data"' in body and '"data":null' not in body:
                    print("检测到历史数据接口响应:", r.url[:120])
                    logged_in = True
                    break
            if logged_in:
                break
            # 信号2：出现新的登录 cookie
            if has_new_login_cookie():
                print("检测到新的登录 cookie")
                logged_in = True
                break
            # 信号3：页头不再显示“请登录”
            if header_logged_in():
                print("检测到页头已登录")
                logged_in = True
                break
            # 如果登录弹窗关闭了且未登录，重新触发查询唤起弹窗
            try:
                if page.locator("iframe").count() == 0 and page.locator("#historykey").is_visible():
                    if not api_resps:
                        page.click("#searchHistory")
            except Exception:
                pass

        if not logged_in:
            print("等待超时，未检测到登录成功")
            browser.close()
            sys.exit(1)

        # 登录成功：再查一次拿数据验证
        if not api_resps:
            try:
                page.fill("#historykey", JD_URL)
                page.click("#searchHistory")
                for _ in range(15):
                    page.wait_for_timeout(1000)
                    if api_resps:
                        break
            except Exception:
                pass

        ctx.storage_state(path=STORAGE)
        print("登录态已保存到:", STORAGE)
        # 打印历史接口响应样例
        for r in api_resps[:2]:
            try:
                print("样例响应:", r.text()[:600])
            except Exception:
                pass
        try:
            page.wait_for_timeout(1000)
            page.screenshot(path=os.path.join(BASE, "shot_after_login.png"))
        except Exception:
            pass
        browser.close()


if __name__ == "__main__":
    main()
