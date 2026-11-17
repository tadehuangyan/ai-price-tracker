# -*- coding: utf-8 -*-
"""第十七轮：
A. 正确编码的普通淘宝链接（无签名）能否查到
B. 京东商品爆料页的签名链接能否查到（checkJdAuth 是否拦截）
"""
import json
import os
import re
from urllib.parse import quote, unquote

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORAGE = os.path.join(BASE, "storage", "manmanbuy_state.json")
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", os.path.join(BASE, "ms-playwright"))

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def query(page, hist_url, wait_sec=22):
    api = []

    def on_resp(r):
        if "tool.manmanbuy.com/api.ashx" in r.url:
            try:
                api.append(r.text())
            except Exception:
                pass

    page.on("response", on_resp)
    page.goto(hist_url, timeout=40000, wait_until="domcontentloaded")
    for _ in range(wait_sec):
        page.wait_for_timeout(1000)
        if api:
            break
    page.remove_listener("response", on_resp)
    return api


def main():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=UA, locale="zh-CN", viewport={"width": 1366, "height": 900},
            storage_state=STORAGE if os.path.exists(STORAGE) else None,
        )
        page = ctx.new_page()

        plain_tb = "http://uland.taobao.com/item/edetail?id=zDBn9dG7cetaeR2oKaziD8HVU4-R5QGDPUXVK5AGWBSp&skuId=6094511691728"

        # A. 无签名、正确编码
        print("== A. 普通链接(正确编码, 无签名) ==")
        url = "https://tool.manmanbuy.com/HistoryLowest.aspx?url=" + quote(plain_tb, safe="")
        api = query(page, url, 20)
        print("响应数:", len(api))
        for b in api[:2]:
            print(" ", b[:800])

        # B. 搜索京东系商品爆料（茅台）
        print("== B. 搜索商品找京东爆料 ==")
        page.goto(
            "https://s.manmanbuy.com/pc/search/result?keyword=%E8%8C%85%E5%8F%B0&c=discount",
            timeout=35000, wait_until="domcontentloaded",
        )
        page.wait_for_timeout(4000)
        links = page.eval_on_selector_all("a[href]", "els => els.map(e=>({t:(e.innerText||'').replace(/\\s+/g,' ').slice(0,40), h:e.href}))")
        deals = [l for l in links if "discuxiao" in l["h"]]
        seen = set()
        uniq = []
        for d in deals:
            if d["h"] not in seen:
                seen.add(d["h"])
                uniq.append(d)
        print("爆料数:", len(uniq))
        for d in uniq[:6]:
            print("  ", d)

        # 打开几个爆料页找签名链接（找 jd 的）
        jd_hist = None
        other_hist = None
        for d in uniq[:6]:
            try:
                page.goto(d["h"], timeout=30000, wait_until="domcontentloaded")
                page.wait_for_timeout(2500)
                hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e=>e.href)")
                signed = [h for h in hrefs if "HistoryLowest.aspx" in h and "st=" in h]
                if signed:
                    target = unquote(re.search(r"url=([^&]+)", signed[0]).group(1))
                    print(f"  爆料 {d['h'][-18:]} -> target: {target[:90]}")
                    if "jd.com" in target and not jd_hist:
                        jd_hist = signed[0]
                    elif "jd.com" not in target and not other_hist:
                        other_hist = signed[0]
                    if jd_hist and other_hist:
                        break
            except Exception as e:
                print("  爆料页失败:", e)

        if jd_hist:
            print("== B1. 京东签名链接查询 ==")
            api = query(page, jd_hist, 18)
            print("响应数:", len(api))
            for b in api[:2]:
                print(" ", b[:800])
        else:
            print("没找到京东爆料签名链接")

        browser.close()


if __name__ == "__main__":
    main()
    print("PROBE17_DONE")
