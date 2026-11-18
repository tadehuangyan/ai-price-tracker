# -*- coding: utf-8 -*-
"""端到端前端验证：登录 -> 各页面截图"""
import os
import sys
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", os.path.join(BASE, "ms-playwright"))

FRONT = os.environ.get("FRONT_URL", "http://localhost:5174")
SHOTS = os.path.join(BASE, "e2e_shots")
# 浏览器 UA 伪装，模拟真实用户访问前端页面
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def main():
    from playwright.sync_api import sync_playwright

    os.makedirs(SHOTS, exist_ok=True)
    errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, locale="zh-CN", viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))

        # 1) 登录页
        page.goto(FRONT + "/login", timeout=30000)
        page.wait_for_timeout(2500)
        page.screenshot(path=os.path.join(SHOTS, "01_login.png"))

        # 2) 管理员登录
        page.fill("input[placeholder*='用户名']", "admin")
        page.fill("input[placeholder='密码']", "admin123456")
        page.click("button:has-text('登 录')")
        page.wait_for_timeout(3000)
        page.screenshot(path=os.path.join(SHOTS, "02_admin_redirect.png"))
        print("登录后URL:", page.url)

        # 3) 首页搜索
        try:
            page.goto(FRONT + "/", timeout=20000)
            page.wait_for_timeout(2500)
            page.fill("input[placeholder*='关键词']", "手机")
            page.keyboard.press("Enter")
            page.wait_for_timeout(2500)
            page.screenshot(path=os.path.join(SHOTS, "03_search.png"))
        except Exception as e:
            print("搜索失败:", e)

        # 4) 商品详情
        try:
            page.click(".grid .item", timeout=5000)
            page.wait_for_timeout(3500)
            page.screenshot(path=os.path.join(SHOTS, "04_detail.png"))
            print("详情URL:", page.url)
        except Exception as e:
            print("打开详情失败:", e)

        # 5) AI 导购（详情页内）
        try:
            page.click("button:has-text('AI 导购分析')", timeout=4000)
            page.wait_for_timeout(5000)
            page.screenshot(path=os.path.join(SHOTS, "05_advisor.png"))
        except Exception as e:
            print("AI导购失败:", e)

        # 6) 价格追踪
        page.goto(FRONT + "/tracking", timeout=20000)
        page.wait_for_timeout(2500)
        page.screenshot(path=os.path.join(SHOTS, "06_tracking.png"))

        # 7) 价格对比
        page.goto(FRONT + "/compare", timeout=20000)
        page.wait_for_timeout(2000)
        page.screenshot(path=os.path.join(SHOTS, "07_compare.png"))

        # 8) AI 导购独立页
        page.goto(FRONT + "/advisor", timeout=20000)
        page.wait_for_timeout(2000)
        page.screenshot(path=os.path.join(SHOTS, "08_advisor_page.png"))

        # 9) 系统管理
        page.goto(FRONT + "/admin", timeout=20000)
        page.wait_for_timeout(3000)
        page.screenshot(path=os.path.join(SHOTS, "09_admin.png"))

        browser.close()

    print("=" * 40)
    print("截图目录:", SHOTS)
    if errors:
        print("控制台错误:")
        for e in errors[:20]:
            print("  -", e[:200])
    else:
        print("无控制台错误")


if __name__ == "__main__":
    main()
    print("E2E_DONE")
