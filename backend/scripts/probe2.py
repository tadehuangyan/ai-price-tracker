# -*- coding: utf-8 -*-
"""第二轮探测：通过真实浏览器操作慢慢买搜索/详情页，抓取历史价格数据结构；
同时探测京东、淘宝商品页价格与反爬情况。"""
import json
import os
import re
import sys

os.environ.setdefault(
    "PLAYWRIGHT_BROWSERS_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ms-playwright"),
)

# 浏览器 UA 伪装，避免被站点识别为自动化工具
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def dump(name, obj):
    """辅助函数：以截断的 JSON 格式打印探测结果"""
    print(f"--- {name} ---")
    print(json.dumps(obj, ensure_ascii=False, indent=1, default=str)[:2500])


def main():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(user_agent=UA, locale="zh-CN", viewport={"width": 1366, "height": 900})
        ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = ctx.new_page()

        # 捕获慢慢买发出的 XHR（寻找历史价格接口）
        api_calls = []
        def on_req(req):
            if "manmanbuy" in req.url and ("json" in (req.resource_type or "") or "History" in req.url or "price" in req.url.lower()):
                api_calls.append(req.url)
        page.on("request", on_req)

        # ===== 慢慢买首页 -> 搜索 =====
        print("[慢慢买] 打开首页")
        try:
            page.goto("https://www.manmanbuy.com/", timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            print("  title:", page.title())
            # 找搜索框
            sel = "input[type=text], input[type=search], #searchbox, .search input"
            box = page.locator(sel).first
            box.fill("机械键盘")
            page.wait_for_timeout(500)
            # 回车或点搜索按钮
            try:
                box.press("Enter")
            except Exception:
                pass
            page.wait_for_timeout(3000)
            print("  搜索后 url:", page.url)
            print("  搜索后 title:", page.title())
            # 收集结果链接
            links = page.eval_on_selector_all(
                "a",
                "els => els.map(e => ({t:(e.innerText||'').trim().slice(0,40), h:e.href}))",
            )
            detail_links = [l for l in links if re.search(r"manmanbuy\.com/(BB|history|detail|tool)", l["h"])]
            for l in detail_links[:10]:
                print("   结果:", l)
        except Exception as e:
            print("  搜索失败:", e)

        # ===== 打开一个历史价格详情页 =====
        target = None
        if detail_links:
            target = detail_links[0]["h"]
        if target:
            print(f"[慢慢买] 打开详情: {target}")
            try:
                page.goto(target, timeout=30000, wait_until="domcontentloaded")
                page.wait_for_timeout(4000)
                print("  title:", page.title())
                html = page.content()
                # 查找价格历史数据
                for pat, desc in [
                    (r"var\s+chartData\s*=\s*(\[.*?\]);", "chartData"),
                    (r"priceList\s*=\s*(\[.*?\]);", "priceList"),
                    (r"hisPrice\s*=\s*(\[.*?\]);", "hisPrice"),
                    (r"\[\s*\d{10,13}\s*,\s*\d+(?:\.\d+)?\s*(?:,\s*\"[^\"]*\")?\s*\]", "时间戳-价格数组"),
                ]:
                    ms = re.findall(pat, html, re.S)
                    if ms:
                        print(f"  找到[{desc}] x{len(ms)}:", str(ms[0])[:300])
                # 页面可见的图表提示/价格文本
                for css in ["#priceHistory", ".hisPrice", ".price", "#chart", "canvas"]:
                    try:
                        n = page.locator(css).count()
                        if n:
                            print(f"  选择器 {css} 命中 {n} 个")
                    except Exception:
                        pass
                # 列出页面中所有 script src 与内联含 price 的片段
                for m in re.finditer(r"([A-Za-z_$]*[Pp]rice[A-Za-z_$]*)\s*[:=]\s*(\[[^\]]{0,200}\]|\"[^\"]{0,80}\")", html):
                    print("   var:", m.group(0)[:200])
            except Exception as e:
                print("  详情失败:", e)
        dump("XHR 抓到的接口", api_calls[:20])

        # ===== 京东 =====
        print("[京东] 商品页")
        try:
            page.goto("https://item.jd.com/100012043978.html", timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(4000)
            print("  title:", page.title())
            for css in [".p-price .price", ".p-price i", ".summary-price .price", ".price.J-p-100012043978"]:
                try:
                    if page.locator(css).count():
                        print(f"  {css} =>", page.locator(css).first.inner_text())
                except Exception:
                    pass
            html = page.content()
            ms = re.findall(r'price["\']?\s*[:=]\s*["\']?(\d+(?:\.\d+)?)', html)
            print("  html price 线索:", ms[:10])
        except Exception as e:
            print("  京东失败:", e)

        # ===== 淘宝 =====
        print("[淘宝] 商品页")
        try:
            page.goto("https://item.taobao.com/item.htm?id=744900933586", timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(4000)
            print("  title:", page.title())
            print("  url:", page.url[:120])
            html = page.content()
            print("  含登录字样:", "登录" in html, "| 含验证码:", "验证码" in html)
            for css in ["[itemprop='price']", ".tb-rmb-num", ".tm-price", ".Price--currentText"]:
                try:
                    if page.locator(css).count():
                        print(f"  {css} =>", page.locator(css).first.inner_text())
                except Exception:
                    pass
        except Exception as e:
            print("  淘宝失败:", e)

        browser.close()


if __name__ == "__main__":
    main()
    print("PROBE2_DONE")
