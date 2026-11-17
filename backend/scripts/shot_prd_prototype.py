# -*- coding: utf-8 -*-
"""截取小程序需求文档中的手机原型区域 -> doc_assets/prd_prototype.png"""
import os

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", os.path.join(BASE, "backend", "ms-playwright"))

HTML = "file:///" + os.path.join(BASE, "商品历史价格追踪系统_小程序端需求文档.html").replace("\\", "/")
OUT = os.path.join(BASE, "doc_assets", "prd_prototype.png")


def main():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=2)
        page.goto(HTML, wait_until="networkidle")
        page.wait_for_timeout(500)
        el = page.query_selector(".phone")
        el.screenshot(path=OUT)
        print("saved:", OUT)
        browser.close()


if __name__ == "__main__":
    main()
