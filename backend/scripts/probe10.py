# -*- coding: utf-8 -*-
"""第十轮：
A. 京东移动商品页真实价格解析（找 JSON 数据）
B. 慢慢买爆料页 -> 原始商品链接提取
"""
import json
import os
import re

os.environ.setdefault(
    "PLAYWRIGHT_BROWSERS_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ms-playwright"),
)

# 浏览器 UA 伪装：移动端与桌面端两套请求头，分别探测移动商品页/爆料页
MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def main():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])

        # ===== A. 京东移动页价格 =====
        print("== A. 京东移动页 ==")
        mctx = browser.new_context(user_agent=MOBILE_UA, locale="zh-CN", viewport={"width": 390, "height": 844})
        mp = mctx.new_page()
        api_resps = []
        mp.on(
            "response",
            lambda r: api_resps.append({"u": r.url, "b": r.text()[:3000]})
            if ("jd.com" in r.url and ("price" in r.url.lower() or "api" in r.url.lower()))
            else None,
        )
        try:
            mp.goto("https://item.m.jd.com/product/100012043978.html", timeout=35000, wait_until="domcontentloaded")
            mp.wait_for_timeout(5000)
            # 找价格相关 JSON
            data = mp.evaluate(
                """() => {
                    const out = {};
                    const html = document.documentElement.innerHTML;
                    // price 字段
                    const pats = [
                        /"price"\\s*:\\s*"?([0-9.]+)"?/g,
                        /"jdPrice"\\s*:\\s*"?([0-9.]+)"?/g,
                        /"realPrice"\\s*:\\s*"?([0-9.]+)"?/g,
                        /"priceText"\\s*:\\s*"([^"]{1,20})"/g,
                        /"skuPrice"\\s*:\\s*"?([0-9.]+)"?/g,
                    ];
                    out.hits = [];
                    for (const p of pats) {
                        let m; let n = 0;
                        while ((m = p.exec(html)) && n < 5) { out.hits.push(m[0].slice(0,80)); n++; }
                    }
                    // 页面可见价格元素
                    out.texts = [];
                    document.querySelectorAll('[class*=price], [class*=Price]').forEach(e => {
                        const t = (e.innerText||'').trim();
                        if (t && t.length < 30 && /\\d/.test(t)) out.texts.push(t);
                    });
                    out.texts = out.texts.slice(0, 15);
                    return out;
                }"""
            )
            print("JSON 命中:", json.dumps(data.get("hits", []), ensure_ascii=False, indent=1))
            print("价格元素:", json.dumps(data.get("texts", []), ensure_ascii=False, indent=1))
            print("price/api 响应:")
            for r in api_resps[:8]:
                print("  ", r["u"][:160])
                print("   ", r["b"][:600])
        except Exception as e:
            print("失败:", e)
        mctx.close()

        # ===== B. 慢慢买爆料页 -> 原始链接 =====
        print("== B. 爆料页原链接 ==")
        ctx = browser.new_context(user_agent=UA, locale="zh-CN", viewport={"width": 1366, "height": 900})
        page = ctx.new_page()
        try:
            page.goto("https://cu.manmanbuy.com/discuxiao_592426771.aspx", timeout=35000, wait_until="domcontentloaded")
            page.wait_for_timeout(3500)
            print("title:", page.title())
            links = page.eval_on_selector_all(
                "a[href]",
                "els => els.map(e=>({t:(e.innerText||'').replace(/\\s+/g,' ').slice(0,30), h:e.href}))",
            )
            plat = [
                l for l in links
                if re.search(r"jd\.com|taobao\.com|tmall\.com|pinduoduo|vip\.com|suning|dangdang", l["h"])
                and "manmanbuy" not in l["h"]
            ]
            print("平台链接:", json.dumps(plat[:10], ensure_ascii=False, indent=1))
            # 跳转链接（redirect/go）
            go = [l for l in links if re.search(r"(go|jump|redirect|url)=|discuxiao.*go", l["h"], re.I)]
            print("跳转链接:", json.dumps(go[:8], ensure_ascii=False, indent=1))
            # 所有 manmanbuy 内部历史链接
            hist = [l for l in links if "HistoryLowest" in l["h"] or "history" in l["h"].lower()]
            print("历史链接:", json.dumps(hist[:5], ensure_ascii=False))
            # 页面文本片段
            txt = page.locator("body").inner_text()
            i = txt.find("历史")
            print("含'历史'文本:", txt[max(0, i - 200): i + 300] if i >= 0 else "无")
        except Exception as e:
            print("失败:", e)

        browser.close()


if __name__ == "__main__":
    main()
    print("PROBE10_DONE")
