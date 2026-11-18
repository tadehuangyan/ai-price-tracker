# -*- coding: utf-8 -*-
"""第五轮：慢慢买历史价格查询流程（输入链接 -> 点查询 -> 抓 api.ashx 响应）"""
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
            if "manmanbuy.com" in resp.url and ("api" in resp.url.lower() or "ashx" in resp.url.lower()):
                try:
                    api_responses.append({"url": resp.url, "body": resp.text()})
                except Exception:
                    pass

        page.on("response", on_resp)

        print("[1] 打开历史价查询页")
        page.goto("https://tool.manmanbuy.com/historyLowest.aspx", timeout=35000, wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
        print("  title:", page.title())

        # 找输入框和查询按钮
        inputs = page.eval_on_selector_all(
            "input",
            "els => els.map((e,i) => ({i, type:e.type, id:e.id, cls:e.className, ph:e.placeholder}))",
        )
        print("  inputs:", json.dumps(inputs, ensure_ascii=False))
        btns = page.eval_on_selector_all(
            "input[type=button], input[type=submit], button, a.btn, .btn",
            "els => els.map((e,i) => ({i, tag:e.tagName, id:e.id, cls:e.className, text:(e.value||e.innerText||'').slice(0,20)}))",
        )
        print("  buttons:", json.dumps(btns, ensure_ascii=False))

        # 输入京东链接并点击查询
        jd_url = "https://item.jd.com/100012043978.html"
        target_input = page.locator("input[type=text]").first
        target_input.fill(jd_url)
        page.wait_for_timeout(300)
        clicked = False
        for label in ["查询历史价格", "查询", "立即查询", "查历史价"]:
            btn = page.get_by_text(label, exact=False).first
            if btn.count() > 0:
                try:
                    btn.click(timeout=3000)
                    clicked = True
                    print("  点击了:", label)
                    break
                except Exception:
                    continue
        if not clicked:
            try:
                page.locator("input[type=submit], input[type=button]").first.click(timeout=3000)
                clicked = True
                print("  点击了 submit/button")
            except Exception as e:
                print("  按钮点击失败:", e)

        # 等待 API 响应
        for _ in range(12):
            page.wait_for_timeout(1000)
            if api_responses:
                break
        print("  url after:", page.url)
        print("  api 响应数:", len(api_responses))
        for r in api_responses[:6]:
            print("  API:", r["url"])
            print("   body:", r["body"][:2000])

        # 页面结果文本
        try:
            text = page.locator("body").inner_text()
            # 截取结果区域
            idx = text.find("历史价格")
            print("  页面文本(片段):\n", text[max(0, idx - 200): idx + 1500])
        except Exception as e:
            print("  文本读取失败:", e)

        # 图表数据兜底：echarts 实例数据
        try:
            data = page.evaluate(
                """() => {
                    const out = {};
                    if (window.chart && window.chart.getOption) {
                        out.series = window.chart.getOption().series.map(s => ({name: s.name, data: (s.data||[]).slice(0,5)}));
                    }
                    // 常见全局变量
                    for (const k of ['priceData','hisPrice','chartData','dataList','trendData']) {
                        if (window[k]) out[k] = JSON.stringify(window[k]).slice(0, 500);
                    }
                    return out;
                }"""
            )
            print("  图表数据:", json.dumps(data, ensure_ascii=False)[:1500])
        except Exception as e:
            print("  图表数据读取失败:", e)

        browser.close()


if __name__ == "__main__":
    main()
    print("PROBE5_DONE")
