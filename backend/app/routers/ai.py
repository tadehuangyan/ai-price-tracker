from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import json
import re

from ..database import get_db
from ..deps import get_current_user
from ..models import Product, User
from ..services import vision
from ..services.ai_advisor import chat_reply, chat_reply_stream
from ..services.moderation import find_injection, find_sensitive

router = APIRouter(prefix="/api/advisor", tags=["AI 智能导购"])

BLOCKED_REPLY = "AI 回复包含敏感内容，已被拦截，请重新提问。"


def _check_input(text: str, db) -> str:
    """输入预检：敏感词 + 提示注入，返回错误信息（空串=放行）"""
    hits = find_sensitive(text, db)
    if hits:
        return f"消息包含敏感词：{'、'.join(hits)}，请修改后重新发送"
    injections = find_injection(text)
    if injections:
        return f"消息包含疑似提示注入指令（{'、'.join(injections)}），已被拦截，请修改后重新发送"
    return ""


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: list = []  # [{role, content}] 最近对话上下文
    product_id: int | None = None  # 路由带入的当前浏览商品
    images: list = []  # [dataURI] 图片以多模态传给模型
    files: list = []  # [{name, url}] 文件信息
    ai_config: dict | None = None  # 用户自定义模型配置 {api_base, api_key, model}，为空走默认


class CheckIn(BaseModel):
    text: str = Field(default="", max_length=4000)


class ImageSearchIn(BaseModel):
    images: list = Field(min_length=1, max_length=4)  # [dataURI]
    ai_config: dict | None = None


@router.post("/check")
def check_text(body: CheckIn, db: Session = Depends(get_db), _=Depends(get_current_user)):
    """发送前预检：命中敏感词/提示注入由前端拦截（不进入对话，弹窗提示）"""
    hits = find_sensitive(body.text, db)
    injections = find_injection(body.text)
    return {"ok": True, "blocked": bool(hits or injections), "hits": hits + injections}


@router.post("/chat")
def chat(body: ChatIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """AI 导购聊天：支持快捷商品 [[product:N]]、商品链接实时抓取、图片、文件"""
    err = _check_input(body.message, db)
    if err:
        return {"ok": False, "error": err}
    ai_config = body.ai_config
    if ai_config is not None:
        missing = [k for k in ("api_base", "api_key", "model") if not (ai_config.get(k) or "").strip()]
        if missing:
            return {"ok": False, "error": "自定义模型配置不完整，请在模型设置中补全或切回默认模型"}
    result = chat_reply(
        db, body.message, body.history, body.product_id,
        images=body.images, files=body.files, ai_config=ai_config, user=user,
    )
    if find_sensitive(result.get("reply") or "", db):
        return {"ok": True, "blocked": True, "reply": BLOCKED_REPLY, "fallback": False}
    return {"ok": True, **result}


@router.post("/chat/stream")
def chat_stream(body: ChatIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """AI 导购聊天（流式 SSE）：增量输出，输出命中敏感词立即中断并替换为违规提示

    事件：data: {"type":"delta","text"} / {"type":"tool","name","status","summary"} /
    {"type":"advice","card"} / {"type":"blocked","reply"} /
    {"type":"done","fallback"} / {"type":"error","message"}
    输入敏感词/注入、配置不完整在开流前以 JSON 返回（{"ok":false,"error"}）。
    """
    err = _check_input(body.message, db)
    if err:
        return {"ok": False, "error": err}
    ai_config = body.ai_config
    if ai_config is not None:
        missing = [k for k in ("api_base", "api_key", "model") if not (ai_config.get(k) or "").strip()]
        if missing:
            return {"ok": False, "error": "自定义模型配置不完整，请在模型设置中补全或切回默认模型"}

    def sse():
        for ev in chat_reply_stream(
            db, body.message, body.history, body.product_id,
            images=body.images, files=body.files, ai_config=ai_config, user=user,
        ):
            if ev.get("type") == "blocked":
                ev = {"type": "blocked", "reply": BLOCKED_REPLY}
            yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        sse(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/upload")
def upload_file(
    file: UploadFile = File(...),
    _=Depends(get_current_user),
):
    """上传文件（发送文件用），保存到 storage/uploads/ 并返回访问地址"""
    import os
    import re as _re
    import time

    safe = _re.sub(r"[^\w.\-\u4e00-\u9fff]", "_", file.filename or "file")
    fname = f"{int(time.time())}_{safe}"
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    updir = os.path.join(base, "storage", "uploads")
    os.makedirs(updir, exist_ok=True)
    with open(os.path.join(updir, fname), "wb") as f:
        f.write(file.file.read())
    # 返回相对路径，跟随页面同源（局域网/内网穿透经前端代理均可访问）
    return {"ok": True, "name": file.filename, "url": f"/uploads/{fname}"}


@router.post("/image_search")
def image_search(body: ImageSearchIn, db: Session = Depends(get_db), _=Depends(get_current_user)):
    """识图找同款（多模态闭环）：图片 -> 视觉模型识别关键词 -> 本地商品库 + 联网候选"""
    try:
        info = vision.image_keywords(body.images, ai_config=body.ai_config)
    except Exception as e:
        return {"ok": False, "error": f"图片识别失败：{e}（可在模型设置中配置支持视觉的模型）"}
    keywords = info.get("keywords") or ""
    if not keywords:
        return {"ok": True, "keywords": "", "candidates": [],
                "message": "未能识别出商品，建议换一张更清晰的正面图"}

    candidates = []
    # 1) 本地商品库候选（关键词命中数排序）
    kws = [k for k in re.split(r"[，,\s]+", keywords) if k][:3]
    if kws:
        from sqlalchemy import or_

        rows = (
            db.query(Product)
            .filter(or_(*[Product.name.like(f"%{k}%") for k in kws]))
            .limit(10)
            .all()
        )
        rows.sort(key=lambda p: -sum(1 for k in kws if k.lower() in (p.name or "").lower()))
        for p in rows[:5]:
            prices = [l.current_price for l in p.listings if l.current_price]
            candidates.append({
                "product_id": p.id, "name": p.name,
                "price": min(prices) if prices else None,
                "image": p.image_url, "platform": "", "url": "", "source": "本地库",
            })
    # 2) 联网候选（慢慢买搜索，失败静默降级为仅本地结果）
    try:
        from ..services.crawler.manmanbuy import discover_products

        for it in (discover_products(keywords, limit=5) or [])[:5]:
            candidates.append({
                "product_id": None, "name": (it.get("title") or "")[:60],
                "price": it.get("price"), "image": it.get("image", ""),
                "platform": it.get("platform", ""), "url": it.get("url", ""), "source": "联网",
            })
    except Exception:
        pass
    return {"ok": True, **info, "keywords": keywords, "candidates": candidates}
