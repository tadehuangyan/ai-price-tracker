# -*- coding: utf-8 -*-
"""第三轮探测：慢慢买搜索结果链接结构 + 详情页历史价格数据；京东移动端/接口"""
import json
import os
import re

os.environ.setdefault(
    "PLAYWRIGHT_BROWSERS_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ms-playwright"),
)

# 浏览器 UA 伪装：桌面端与移动端两套请求头，分别探测 PC/移动页面
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
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
            lambda r: xhrs.append(r.url)
            if ("manmanbuy" in r.url and r.resource_type in ("xhr", "fetch"))
            else None,
        )

        # ===== 慢慢买搜索结果：链接结构 =====
        print("[慢慢买] 搜索结果链接")
        page.goto(
            "https://s.manmanbuy.com/pc/search/result?keyword=%E6%9C%BA%E6%A2%B0%E9%94%AE%E7%9B%98",
            timeout=30000,
            wait_until="domcontentloaded",
        )
        page.wait_for_timeout(4000)
        links = page.eval_on_selector_all(
            "a[href]",
            "els => els.map(e => ({t:(e.innerText||'').replace(/\\s+/g,' ').trim().slice(0,60), h:e.href}))",
        )
        seen = set()
        detail = []
        for l in links:
            if "manmanbuy.com" in l["h"] and l["h"] not in seen:
                seen.add(l["h"])
                if not re.search(r"(search|keywords|login|about|help|www\.manmanbuy\.com/?$)", l["h"]):
                    detail.append(l)
        for l in detail[:15]:
            print("  ", l)

        # 也抓卡片上的链接（可能在 shadow/JS 里）
        cards = page.eval_on_selector_all(
            "[class*=item] a, [class*=goods] a, [class*=product] a",
            "els => els.slice(0,20).map(e => ({t:(e.innerText||'').replace(/\\s+/g,' ').slice(0,40), h:e.href}))",
        )
        print("  卡片链接:", json.dumps(cards[:10], ensure_ascii=False))

        # ===== 打开详情/历史价格页 =====
        target = None
        for l in detail:
            if re.search(r"/(BB|history|detail|jd|taobao|item)", l["h"]):
                target = l["h"]
                break
        if not target and detail:
            target = detail[0]["h"]
        print("[慢慢买] 详情页:", target)
        if target:
            xhrs.clear()
            page.goto(target, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(5000)
            print("  title:", page.title())
            print("  url:", page.url)
            html = page.content()
            # 查找价格历史数据
            patterns = [
                r"(chartData|priceList|hisPrice|priceHistory|dataList)\s*=\s*(\[[\s\S]{0,400}?\])\s*;",
                r"\[\s*['\"]?\d{4}-\d{2}-\d{2}['\"]?\s*,\s*\d+(?:\.\d+)?\s*(?:,[^\]]*)?\]",
                r"(\d{4}-\d{2}-\d{2})['\"]?\s*[,:]\s*['\"]?(\d+(?:\.\d+)?)",
            ]
            for pat in patterns:
                ms = re.findall(pat, html)
                if ms:
                    print("  命中:", str(ms[:3])[:500])
            # canvas/echarts?
            for css in ["canvas", "#container", "#chart", ".chart", "[class*=chart]", "[class*=history]"]:
                try:
                    n = page.locator(css).count()
                    if n:
                        print(f"  选择器 {css}: {n}")
                except Exception:
                    pass
            # 内联脚本里含 price 的变量
            for m in list(re.finditer(r"(?:var\s+)?([A-Za-z_$][\w$]*[Pp]rice[\w$]*)\s*=\s*(\[[\s\S]{0,300}?\]|\"[^\"]{0,100}\"|\d+(?:\.\d+)?)", html))[:15]:
                print("   变量:", m.group(0)[:250].replace("\n", " "))
            print("  XHR:", json.dumps(xhrs[:15], ensure_ascii=False, indent=1))

            # 页面文本中的“历史价格”提示
            try:
                body_text = page.locator("body").inner_text()[:1500]
                print("  页面文本片段:\n", body_text[:800])
            except Exception:
                pass

        # ===== 京东移动端 =====
        print("[京东] 移动端商品页")
        mctx = browser.new_context(user_agent=MOBILE_UA, locale="zh-CN", viewport={"width": 390, "height": 844})
        mp = mctx.new_page()
        try:
            mp.goto("https://item.m.jd.com/product/100012043978.html", timeout=30000, wait_until="domcontentloaded")
            mp.wait_for_timeout(4000)
            print("  title:", mp.title())
            print("  url:", mp.url[:120])
            mhtml = mp.content()
            print("  price 线索:", re.findall(r'price["\']?\s*[:=]\s*["\']?(\d+(?:\.\d+)?)', mhtml)[:8])
            try:
                txt = mp.locator("body").inner_text()[:600]
                print("  文本:\n", txt[:500])
            except Exception:
                pass
        except Exception as e:
            print("  移动端失败:", e)
        mctx.close()

        # ===== 京东价格接口（浏览器上下文内请求）=====
        print("[京东] 浏览器内请求价格接口")
        try:
            resp = ctx.request.get(
                "https://p.3.cn/prices/mgets",
                params={"type": 1, "skuIds": "J_100012043978"},
                headers={"Referer": "https://item.jd.com/"},
                timeout=15000,
            )
            print("  status:", resp.status, resp.text()[:200])
        except Exception as e:
            print("  接口失败:", e)

        browser.close()


if __name__ == "__main__":
    main()
    print("PROBE3_DONE")
