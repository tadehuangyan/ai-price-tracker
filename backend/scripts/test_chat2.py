# -*- coding: utf-8 -*-
"""测试：文件上传 / 图片多模态聊天"""
import base64
import os
import sys
import time

import httpx

BASE = "http://127.0.0.1:8000"


def main():
    c = httpx.Client(base_url=BASE, timeout=120)
    tok = c.post("/api/auth/login", json={"username": "admin", "password": "admin123456"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}

    # 1) 文件上传
    tmp = os.path.join(os.path.dirname(__file__), "_tmp_upload.txt")
    with open(tmp, "wb") as f:
        f.write("测试文件内容 - SPT".encode("utf-8"))
    with open(tmp, "rb") as f:
        r = c.post("/api/advisor/upload", files={"file": ("测试文档.txt", f, "text/plain")}, headers=h).json()
    os.remove(tmp)
    print("[1] 文件上传:", r)
    # 静态访问验证
    if r.get("ok"):
        vr = c.get(r["url"].replace(BASE, ""))
        print("   静态访问:", vr.status_code, vr.text[:30])

    # 2) 图片多模态聊天（用项目里的截图）
    img_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shot_after_login.png")
    if os.path.exists(img_path):
        b64 = base64.b64encode(open(img_path, "rb").read()).decode()
        data_uri = f"data:image/png;base64,{b64}"
        t0 = time.time()
        r = c.post(
            "/api/advisor/chat",
            json={
                "message": "这是什么图片？简单描述一下",
                "history": [],
                "images": [data_uri],
            },
            headers=h,
        ).json()
        print(f"[2] 图片聊天 {time.time()-t0:.1f}s fallback={r['fallback']}")
        print("   AI:", r["reply"][:300].replace("\n", " / "))
    else:
        print("[2] 跳过：无测试图片")

    # 3) 文件消息聊天
    t0 = time.time()
    r = c.post(
        "/api/advisor/chat",
        json={
            "message": "你好",
            "history": [],
            "files": [{"name": "测试文档.txt", "url": r.get("url", "")}],
        },
        headers=h,
    ).json()
    print(f"[3] 文件消息 {time.time()-t0:.1f}s fallback={r['fallback']}")
    print("   AI:", r["reply"][:200].replace("\n", " / "))

    print("ALL_DONE")


if __name__ == "__main__":
    sys.exit(main())
