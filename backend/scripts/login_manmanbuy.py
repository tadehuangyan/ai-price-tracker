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

# 浏览器 UA 伪装，与后续采集脚本保持一致，避免登录态因 UA 不一致失效
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

        # 打开页面并触发登录弹窗（先加载完，让常规 cookie 种下）
        page.goto("https://tool.manmanbuy.com/HistoryLowest.aspx", timeout=40000, wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
        page.fill("#historykey", JD_URL)
        page.click("#searchHistory")
        page.wait_for_timeout(3500)

        # 基线 cookie 必须在页面完全加载后再抓，否则会把 session/csrf 误判为登录 cookie
        base_cookies = {c["name"] for c in ctx.cookies()}

        def has_new_login_cookie():
            names = {c["name"] for c in ctx.cookies()}
            new = names - base_cookies
            # 登录后通常会出现用户相关 cookie（排除统计/性能类）
            ignore = ("Hm_lvt", "Hm_lpvt", "_ga", "_gid", "_gat", "ASP.NET_SessionId")
            return any(not any(i in n for i in ignore) for n in new)

        def header_logged_in():
            """页头出现『退出』类字样才是真登录（仅『请登录消失』易误判）"""
            try:
                t = page.locator("body").inner_text()[:800]
                return ("退出" in t) or ("退出登录" in t) or ("我的订单" in t) or ("个人中心" in t)
            except Exception:
                return False

        print("=" * 60)
        print("请在打开的浏览器窗口中完成登录（可能弹出微信扫码框）")
        print("登录成功后脚本会自动保存登录态并退出（最多等 5 分钟）")
        print("=" * 60)
        sys.stdout.flush()

        deadline = time.time() + 300  # 5 分钟
        logged_in = False
        tick = 0
        while time.time() < deadline:
            page.wait_for_timeout(2000)
            tick += 1
            # 只信『新登录 cookie』或『页头出现退出/我的』——匿名接口返回数据不算登录
            if has_new_login_cookie():
                print("检测到新的登录 cookie")
                logged_in = True
                break
            if header_logged_in():
                print("检测到页头已登录")
                logged_in = True
                break
            if tick % 5 == 0:
                print("等待扫码登录中...（请在浏览器窗口内完成登录）")
                sys.stdout.flush()

        if not logged_in:
            print("等待超时，未检测到登录成功")
            browser.close()
            sys.exit(1)

        # 登录成功：保存登录态
        ctx.storage_state(path=STORAGE)
        print("登录态已保存到:", STORAGE)
        try:
            page.wait_for_timeout(1000)
            page.screenshot(path=os.path.join(BASE, "shot_after_login.png"))
        except Exception:
            pass
        browser.close()


if __name__ == "__main__":
    main()
