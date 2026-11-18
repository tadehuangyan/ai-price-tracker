# -*- coding: utf-8 -*-
"""第六轮：慢慢买 #historykey + #searchHistory 精确查询，抓 api.ashx 响应"""
import json
import os

os.environ.setdefault(
    "PLAYWRIGHT_BROWSERS_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ms-playwright"),
)

# 浏览器 UA 伪装，避免被站点识别为自动化工具
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def main():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(user_agent=UA, locale="zh-CN", viewport={"width": 1366, "height": 900})
        ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = ctx.new_page()

        api_responses = []

        def on_resp(resp):
            if "manmanbuy.com" in resp.url and ("ashx" in resp.url or "/api" in resp.url):
                try:
                    api_responses.append({"url": resp.url, "body": resp.text()})
                except Exception:
                    pass

        page.on("response", on_resp)

        page.goto("https://tool.manmanbuy.com/historyLowest.aspx", timeout=35000, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        jd_url = "https://item.jd.com/100012043978.html"
        page.fill("#historykey", jd_url)
        page.click("#searchHistory")
        print("已点击查询，等待响应...")

        for i in range(20):
            page.wait_for_timeout(1000)
            if api_responses:
                # 再多等 3 秒收集后续请求
                page.wait_for_timeout(3000)
                break
            if i == 8:
                print("  8s 无响应，当前 url:", page.url)

        print("api 响应数:", len(api_responses))
        for r in api_responses[:8]:
            print("API:", r["url"])
            print(" body:", r["body"][:3000])
            print()

        print("最终 url:", page.url)
        try:
            text = page.locator("body").inner_text()
            idx = text.find("历史价格")
            print("页面文本片段:\n", text[max(0, idx - 100): idx + 1800])
        except Exception as e:
            print("文本失败:", e)

        # 全局变量兜底
        try:
            data = page.evaluate(
                """() => {
                    const out = {};
                    const keys = ['priceData','hisPrice','chartData','dataList','trendData','history','option'];
                    for (const k of keys) {
                        try { if (window[k]) out[k] = JSON.stringify(window[k]).slice(0, 600); } catch(e) {}
                    }
                    // echarts 全局实例
                    try {
                        const els = document.querySelectorAll('canvas');
                        out.canvasCount = els.length;
                    } catch(e) {}
                    return out;
                }"""
            )
            print("全局数据:", json.dumps(data, ensure_ascii=False)[:2000])
        except Exception as e:
            print("全局数据失败:", e)

        browser.close()


if __name__ == "__main__":
    main()
    print("PROBE6_DONE")
