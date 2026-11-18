# -*- coding: utf-8 -*-
"""验证京东移动页价格 JSON 完整值"""
import json
import os

os.environ.setdefault(
    "PLAYWRIGHT_BROWSERS_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ms-playwright"),
)

# 移动端 UA 伪装，模拟 iPhone 浏览器访问京东移动商品页
MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)


def main():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=MOBILE_UA, locale="zh-CN", viewport={"width": 390, "height": 844})
        page = ctx.new_page()
        page.goto("https://item.m.jd.com/product/100012043978.html", timeout=35000, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
        out = page.evaluate(
            r"""() => {
                const html = document.documentElement.innerHTML;
                const res = [];
                const pats = [/"price"\s*:\s*"?([\d.,]+)"?/g, /"jdPrice"\s*:\s*"?([\d.,]+)"?/g, /"originalPrice"\s*:\s*"?([\d.,]+)"?/g, /"appPrice"\s*:\s*"?([\d.,]+)"?/g];
                for (const p of pats) {
                    let m, n = 0;
                    while ((m = p.exec(html)) && n < 6) { res.push(m[0].slice(0, 100)); n++; }
                }
                return res;
            }"""
        )
        print(json.dumps(out, ensure_ascii=False, indent=1))
        browser.close()


if __name__ == "__main__":
    main()
    print("PROBE11_DONE")
