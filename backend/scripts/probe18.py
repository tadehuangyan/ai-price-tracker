# -*- coding: utf-8 -*-
"""第十八轮：登录态下 c=search 全网商品比价结果结构（同款多平台报价）"""
import json
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORAGE = os.path.join(BASE, "storage", "manmanbuy_state.json")
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", os.path.join(BASE, "ms-playwright"))

# 浏览器 UA 伪装，与登录时保持一致避免会话校验差异
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def main():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=UA, locale="zh-CN", viewport={"width": 1366, "height": 1600},
            storage_state=STORAGE if os.path.exists(STORAGE) else None,
        )
        page = ctx.new_page()
        xhrs = []
        page.on(
            "request",
            lambda r: xhrs.append({"m": r.method, "u": r.url, "post": (r.post_data or "")[:300]})
            if (r.resource_type in ("xhr", "fetch") and "manmanbuy" in r.url)
            else None,
        )
        resps = []
        page.on(
            "response",
            lambda r: resps.append({"u": r.url, "b": r.text()[:4000]})
            if (r.request.resource_type in ("xhr", "fetch") and "manmanbuy" in r.url)
            else None,
        )

        page.goto(
            "https://s.manmanbuy.com/pc/search/result?keyword=%E6%9C%BA%E6%A2%B0%E9%94%AE%E7%9B%98&c=search",
            timeout=35000, wait_until="domcontentloaded",
        )
        page.wait_for_timeout(5000)
        page.screenshot(path=os.path.join(BASE, "shot_p18.png"))
        print("title:", page.title())

        # 商品卡片结构
        cards = page.evaluate(
            r"""() => {
                const out = [];
                const nodes = document.querySelectorAll('li, div');
                for (const n of nodes) {
                    const t = (n.innerText || '').trim();
                    if (t.length > 30 && t.length < 600 && /￥|¥|\d+\.\d{2}/.test(t) && n.querySelector('a[href]')) {
                        const links = Array.from(n.querySelectorAll('a[href]')).map(a=>a.href);
                        if (links.some(h => /HistoryLowest|discuxiao|BB\d+|product/.test(h))) {
                            out.push({cls:(n.className||'').toString().slice(0,50), text: t.replace(/\n/g,' | ').slice(0,250), links: links.slice(0,3)});
                            if (out.length >= 8) break;
                        }
                    }
                }
                return out;
            }"""
        )
        print("卡片:", json.dumps(cards, ensure_ascii=False, indent=1)[:4000])

        print("XHR:", json.dumps([x["u"][:130] for x in xhrs[:20]], ensure_ascii=False, indent=1))
        for r in resps[:6]:
            print("RESP", r["u"][:140])
            print("   ", r["b"][:1200])

        browser.close()


if __name__ == "__main__":
    main()
    print("PROBE18_DONE")
