# -*- coding: utf-8 -*-
"""第十二轮：c=search 商品卡片结构（滚动加载后）"""
import json
import os
import re

os.environ.setdefault(
    "PLAYWRIGHT_BROWSERS_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ms-playwright"),
)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def main():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, locale="zh-CN", viewport={"width": 1366, "height": 2000})
        page = ctx.new_page()
        xhrs = []
        page.on(
            "request",
            lambda r: xhrs.append({"m": r.method, "u": r.url, "post": (r.post_data or "")[:300]})
            if ("manmanbuy" in r.url and r.resource_type in ("xhr", "fetch"))
            else None,
        )

        page.goto(
            "https://s.manmanbuy.com/pc/search/result?keyword=%E6%9C%BA%E6%A2%B0%E9%94%AE%E7%9B%98&c=search",
            timeout=35000,
            wait_until="domcontentloaded",
        )
        page.wait_for_timeout(4000)
        # 滚动触发懒加载
        for _ in range(4):
            page.mouse.wheel(0, 1500)
            page.wait_for_timeout(1200)
        page.wait_for_timeout(2000)

        # 商品卡片：找含价格的容器
        cards = page.evaluate(
            r"""() => {
                const out = [];
                // 常见商品卡结构
                const nodes = document.querySelectorAll('li, div');
                for (const n of nodes) {
                    const t = (n.innerText || '').trim();
                    if (t.length > 20 && t.length < 400 && /￥|¥|\d+\.\d{2}元/.test(t) && n.querySelector('a')) {
                        const a = n.querySelector('a');
                        out.push({cls: (n.className||'').toString().slice(0,60), text: t.replace(/\n/g,' | ').slice(0,200), href: a.href});
                        if (out.length >= 12) break;
                    }
                }
                return out;
            }"""
        )
        print("卡片:", json.dumps(cards, ensure_ascii=False, indent=1))

        # 所有链接的路径模式
        links = page.eval_on_selector_all(
            "a[href]",
            "els => els.map(e=>({t:(e.innerText||'').replace(/\\s+/g,' ').slice(0,40), h:e.href}))",
        )
        paths = {}
        for l in links:
            m = re.match(r"https?://([\w.-]*manmanbuy\.com)(/[^?#]*)", l["h"])
            if m:
                key = m.group(1) + re.sub(r"\d+", "N", m.group(2))[:60]
                paths.setdefault(key, 0)
                paths[key] += 1
        print("路径模式:", json.dumps(paths, ensure_ascii=False, indent=1))

        # 商品类链接（非导航/爆料）
        goods = [
            l for l in links
            if re.search(r"(BB\d+|/product|/goods|/item|/detail|compare|bijia)", l["h"], re.I)
        ]
        print("商品类链接:", json.dumps(goods[:15], ensure_ascii=False, indent=1))

        print("XHR:", json.dumps(xhrs[:15], ensure_ascii=False, indent=1))
        try:
            page.screenshot(path=os.path.join(os.path.dirname(__file__), "..", "shot_search.png"), full_page=False)
        except Exception:
            pass
        browser.close()


if __name__ == "__main__":
    main()
    print("PROBE12_DONE")
