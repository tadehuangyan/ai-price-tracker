# -*- coding: utf-8 -*-
"""第八轮：c=search 比价搜索 -> 商品页 -> 历史价格数据"""
import json
import os
import re

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

        xhrs = []
        page.on(
            "request",
            lambda r: xhrs.append({"m": r.method, "u": r.url, "post": (r.post_data or "")[:200]})
            if ("manmanbuy" in r.url and r.resource_type in ("xhr", "fetch"))
            else None,
        )
        responses = []
        page.on(
            "response",
            lambda r: responses.append({"u": r.url, "b": r.text()[:3000]})
            if ("manmanbuy" in r.url and ("ashx" in r.url or "api" in r.url.lower()))
            else None,
        )

        # ===== 比价搜索 =====
        url = "https://s.manmanbuy.com/pc/search/result?keyword=%E6%9C%BA%E6%A2%B0%E9%94%AE%E7%9B%98&c=search"
        print("== 比价搜索 ==")
        page.goto(url, timeout=35000, wait_until="domcontentloaded")
        page.wait_for_timeout(4000)
        print("title:", page.title())
        links = page.eval_on_selector_all(
            "a[href]",
            "els => els.map(e=>({t:(e.innerText||'').replace(/\\s+/g,' ').slice(0,50), h:e.href}))",
        )
        # 商品页链接候选
        cands = []
        for l in links:
            h = l["h"]
            if not h.startswith("http"):
                continue
            if re.search(r"manmanbuy\.com/(BB\d|product|goods|detail|item)", h) and "search" not in h:
                cands.append(l)
        print("商品页候选:", json.dumps(cands[:10], ensure_ascii=False))
        # 非导航类链接统计（找出新路径模式）
        paths = {}
        for l in links:
            m = re.match(r"https?://([\w.]*manmanbuy\.com)(/[^?#]*)", l["h"])
            if m:
                key = m.group(1) + re.sub(r"\d+", "N", m.group(2))[:50]
                paths.setdefault(key, 0)
                paths[key] += 1
        print("路径模式:", json.dumps(paths, ensure_ascii=False, indent=1))

        # 若没有明显商品页，取卡片商品链接（通常带 itemid / go 跳转）
        if not cands:
            # 打印前 40 个链接看看
            for l in links[:40]:
                print("  ", l)

        # ===== 打开第一个商品页 =====
        target = cands[0]["h"] if cands else None
        if target:
            xhrs.clear()
            responses.clear()
            print("== 商品页:", target)
            page.goto(target, timeout=35000, wait_until="domcontentloaded")
            page.wait_for_timeout(6000)
            print("title:", page.title())
            text = page.locator("body").inner_text()
            print("文本片段:\n", text[:1500])
            print("XHR:", json.dumps(xhrs[:15], ensure_ascii=False, indent=1))
            print("API 响应:")
            for r in responses[:8]:
                print("  ", r["u"][:150])
                print("   ", r["b"][:1500])
            html = page.content()
            for pat in [r"\[\s*\d{4}-\d{2}-\d{2}\s*,\s*\d+(?:\.\d+)?", r"price[A-Za-z]*\s*=\s*\["]:
                ms = re.findall(pat, html)
                if ms:
                    print("html 模式命中:", pat, ms[:3])
            # 全局变量
            g = page.evaluate(
                """() => {
                    const out = {};
                    const keys = ['priceData','hisPrice','chartData','dataList','trendData','history','hisList','priceList'];
                    for (const k of keys) { try { if (window[k]) out[k] = JSON.stringify(window[k]).slice(0,800);} catch(e){} }
                    out.canvas = document.querySelectorAll('canvas').length;
                    return out;
                }"""
            )
            print("全局:", json.dumps(g, ensure_ascii=False)[:2000])

        browser.close()


if __name__ == "__main__":
    main()
    print("PROBE8_DONE")
