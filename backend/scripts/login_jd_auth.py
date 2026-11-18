# -*- coding: utf-8 -*-
"""京东授权助手：打开慢慢买历史价格页（京东商品），保持“京东授权”二维码窗口打开，
请用【慢慢买 APP】扫码完成京东授权。授权成功后自动保存登录态并验证京东历史查询。

运行: python scripts/login_jd_auth.py
"""
import json
import os
import sys
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORAGE = os.path.join(BASE, "storage", "manmanbuy_state.json")
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", os.path.join(BASE, "ms-playwright"))

# 浏览器 UA 伪装，与采集脚本保持一致避免登录态失效
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
JD_URL = "https://item.jd.com/100012043978.html"
TIMEOUT_SEC = 480  # 8 分钟


def main():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,  # 可见窗口
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            user_agent=UA, locale="zh-CN", viewport={"width": 1280, "height": 860},
            storage_state=STORAGE if os.path.exists(STORAGE) else None,
        )
        ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = ctx.new_page()

        api_resps = []

        def on_resp(r):
            if "tool.manmanbuy.com/api.ashx" in r.url:
                try:
                    body = r.text()
                    api_resps.append(body)
                except Exception:
                    pass

        page.on("response", on_resp)

        print("=" * 64)
        print("请在打开的浏览器窗口中操作：")
        print("  1. 页面会弹出【京东授权】二维码")
        print("  2. 用【慢慢买 APP】扫码完成京东授权")
        print("  3. 授权完成后脚本会自动验证并保存（窗口请勿关闭）")
        print("=" * 64)
        sys.stdout.flush()

        page.goto("https://tool.manmanbuy.com/HistoryLowest.aspx", timeout=40000, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        page.fill("#historykey", JD_URL)
        page.click("#searchHistory")

        auth_url = ""
        deadline = time.time() + TIMEOUT_SEC
        verified = False

        while time.time() < deadline:
            page.wait_for_timeout(2000)

            # 检查京东授权状态
            try:
                resp = ctx.request.get(
                    "https://tool.manmanbuy.com/HistoryLowest.aspx?action=checkJdAuth",
                    headers={"Referer": "https://tool.manmanbuy.com/HistoryLowest.aspx"},
                    timeout=10000,
                )
                data = resp.json()
                auth = (data.get("data") or {}).get("auth")
                if auth:
                    print("京东授权状态: 已授权 ✓")
                    # 授权成功：重新查询验证
                    try:
                        page.fill("#historykey", JD_URL)
                        page.click("#searchHistory")
                    except Exception:
                        pass
                    for _ in range(20):
                        page.wait_for_timeout(1000)
                        if any('"haveTrend"' in b and '"code":0' in b for b in api_resps):
                            verified = True
                            break
                    if verified:
                        break
                else:
                    auth_url = (data.get("data") or {}).get("authUrl") or auth_url
            except Exception:
                pass

            # 授权弹窗出现时提示（不关闭它）
            try:
                if page.get_by_text("京东授权").count() > 0 and page.get_by_text("京东授权").first.is_visible():
                    print("[等待扫码] 京东授权二维码显示中，请用慢慢买 APP 扫码…")
                    sys.stdout.flush()
            except Exception:
                pass

        if not verified:
            # 最后再等一次数据
            for _ in range(10):
                page.wait_for_timeout(1000)
                if any('"haveTrend"' in b and '"code":0' in b for b in api_resps):
                    verified = True
                    break

        ctx.storage_state(path=STORAGE)
        print("登录态已保存:", STORAGE)
        if verified:
            print("京东历史价格验证通过 ✓")
            for b in api_resps:
                if '"haveTrend"' in b:
                    print("样例:", b[:500])
                    break
        else:
            print("未检测到授权完成（可能超时或授权未通过）")
            print("authUrl:", auth_url)
        try:
            page.screenshot(path=os.path.join(BASE, "shot_jd_auth.png"))
        except Exception:
            pass
        browser.close()
        sys.exit(0 if verified else 1)


if __name__ == "__main__":
    main()
