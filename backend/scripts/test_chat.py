# -*- coding: utf-8 -*-
"""聊天接口端到端测试：普通对话 / 商品 / 链接"""
import sys
import time

import httpx

BASE = "http://127.0.0.1:8000"


def main():
    c = httpx.Client(base_url=BASE, timeout=120)
    tok = c.post("/api/auth/login", json={"username": "admin", "password": "admin123456"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}

    # 1) 普通聊天
    t0 = time.time()
    r = c.post("/api/advisor/chat", json={"message": "你好，你能帮我做什么？", "history": []}, headers=h).json()
    print(f"[1] 普通聊天 {time.time()-t0:.1f}s fallback={r['fallback']} contexts={len(r['contexts'])}")
    print("  AI:", r["reply"][:250].replace("\n", " / "))
    print()

    # 2) 带商品
    t0 = time.time()
    r = c.post(
        "/api/advisor/chat",
        json={"message": "[[product:1]] 这个商品现在值得买吗？", "history": []},
        headers=h,
    ).json()
    print(f"[2] 商品聊天 {time.time()-t0:.1f}s fallback={r['fallback']} contexts={len(r['contexts'])}")
    print("  AI:", r["reply"][:400].replace("\n", " / "))
    print()

    # 3) 带链接（实时抓取，较慢）
    t0 = time.time()
    link = "https://detail.tmall.com/item.htm?id=703915430661&skuId=5136580159880"
    r = c.post(
        "/api/advisor/chat",
        json={"message": f"帮我看看这个链接的商品 {link}", "history": []},
        headers=h,
    ).json()
    print(f"[3] 链接聊天 {time.time()-t0:.1f}s fallback={r['fallback']} contexts={len(r['contexts'])}")
    for ctx in r["contexts"]:
        print("  上下文:", ctx[:150].replace("\n", " | "))
    print("  AI:", r["reply"][:400].replace("\n", " / "))

    print()
    print("ALL_DONE")


if __name__ == "__main__":
    sys.exit(main())
