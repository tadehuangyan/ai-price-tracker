# -*- coding: utf-8 -*-
"""技术文档截图采集：登录 -> 各核心页面/AI 交互场景截图

运行: python scripts/shot_doc.py
输出: doc_assets/screenshots/*.png（1440x900，文档插图用）
"""
import os
import sys
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", os.path.join(BASE, "ms-playwright"))

FRONT = os.environ.get("FRONT_URL", "http://localhost:5174")
SHOTS = os.path.join(os.path.dirname(BASE), "doc_assets", "screenshots")
# 浏览器 UA 伪装，模拟真实用户访问前端页面
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def main():
    from playwright.sync_api import sync_playwright

    os.makedirs(SHOTS, exist_ok=True)
    errors = []

    def shot(page, name):
        """辅助函数：截取当前页面并按名称保存到截图目录"""
        page.screenshot(path=os.path.join(SHOTS, f"{name}.png"))
        print("[截图]", name)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, locale="zh-CN", viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

        # 1) 登录页
        page.goto(FRONT + "/login", timeout=30000)
        page.wait_for_timeout(2500)
        shot(page, "01_login")

        # 2) 登录（管理员，覆盖全部页面）
        page.fill("input[placeholder*='用户名']", "admin")
        page.fill("input[placeholder='密码']", "admin123456")
        page.click("button:has-text('登 录')")
        page.wait_for_timeout(3000)

        # 3) 首页（采集台 + 标本展位）
        page.goto(FRONT + "/", timeout=30000)
        page.wait_for_timeout(4500)
        shot(page, "02_home")

        # 4) 商品详情（价格呼吸图谱）
        page.goto(FRONT + "/product/23", timeout=30000)
        page.wait_for_timeout(3500)
        shot(page, "03_product_detail")

        # 5) AI 导购：带商品自动提问 -> 建议卡 + 数据分析（真实大模型）
        page.goto(FRONT + "/advisor?product=23&q=%E8%BF%99%E5%8F%B0%E5%80%BC%E5%BE%97%E4%B9%B0%E5%90%97", timeout=30000)
        page.wait_for_timeout(45000)  # 等待建议卡 + 流式回复完成
        shot(page, "04_advisor_advice_card")

        # 6) AI 导购：Agent 工具调用 + 行情（真实大模型）
        try:
            page.fill(".input-main textarea", "帮我查下现在内存条的行情，值得入手吗")
            page.keyboard.press("Enter")
            page.wait_for_timeout(50000)  # 工具调用 + 流式作答
            shot(page, "05_advisor_agent_tools")
        except Exception as e:
            print("AI 行情演示截图失败:", e)

        # 7) 用户画像（个人中心）
        try:
            page.goto(FRONT + "/profile", timeout=20000)
            page.wait_for_timeout(2000)
            page.click("text=用户画像")
            page.wait_for_timeout(1500)
            shot(page, "06_profile_memo")
        except Exception as e:
            print("画像截图失败:", e)

        # 8) 价格对比（比价台 + 三张图）
        try:
            page.goto(FRONT + "/compare?ids=23,46,51", timeout=20000)
            page.wait_for_timeout(4000)
            shot(page, "07_compare")
        except Exception as e:
            print("比价截图失败:", e)

        # 9) 价格追踪
        page.goto(FRONT + "/tracking", timeout=20000)
        page.wait_for_timeout(2500)
        shot(page, "08_tracking")

        # 10) 管理端（知识库 Tab：RAG 管理）
        try:
            page.goto(FRONT + "/admin", timeout=20000)
            page.wait_for_timeout(2500)
            page.click("text=知识库")
            page.wait_for_timeout(1500)
            shot(page, "09_admin_knowledge")
        except Exception as e:
            print("管理端截图失败:", e)

        # 11) 历史对话抽屉
        try:
            page.goto(FRONT + "/advisor", timeout=20000)
            page.wait_for_timeout(2500)
            page.click("button:has-text('历史对话')")
            page.wait_for_timeout(1200)
            shot(page, "10_advisor_history")
        except Exception as e:
            print("历史对话截图失败:", e)

        browser.close()

    print("=" * 40)
    print("截图目录:", SHOTS)
    if errors:
        print("控制台错误:", len(errors))
        for e in errors[:5]:
            print("  -", e[:150])
    print("SHOT_DONE")


if __name__ == "__main__":
    main()
