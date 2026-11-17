from fastapi import APIRouter, Depends, File, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import User
from ..services.ai_advisor import chat_reply
from ..services.moderation import find_sensitive

router = APIRouter(prefix="/api/advisor", tags=["AI 智能导购"])

BLOCKED_REPLY = "AI 回复包含敏感内容，已被拦截，请重新提问。"


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: list = []  # [{role, content}] 最近对话上下文
    product_id: int | None = None  # 路由带入的当前浏览商品
    images: list = []  # [dataURI] 图片以多模态传给模型
    files: list = []  # [{name, url}] 文件信息
    ai_config: dict | None = None  # 用户自定义模型配置 {api_base, api_key, model}，为空走默认


@router.post("/chat")
def chat(body: ChatIn, db: Session = Depends(get_db), _=Depends(get_current_user)):
    """AI 导购聊天：支持快捷商品 [[product:N]]、商品链接实时抓取、图片、文件"""
    hits = find_sensitive(body.message, db)
    if hits:
        return {"ok": False, "error": f"消息包含敏感词：{'、'.join(hits)}，请修改后重新发送"}
    ai_config = body.ai_config
    if ai_config is not None:
        missing = [k for k in ("api_base", "api_key", "model") if not (ai_config.get(k) or "").strip()]
        if missing:
            return {"ok": False, "error": "自定义模型配置不完整，请在模型设置中补全或切回默认模型"}
    result = chat_reply(
        db, body.message, body.history, body.product_id,
        images=body.images, files=body.files, ai_config=ai_config,
    )
    if find_sensitive(result.get("reply") or "", db):
        return {"ok": True, "blocked": True, "reply": BLOCKED_REPLY, "fallback": False}
    return {"ok": True, **result}


@router.post("/upload")
def upload_file(
    file: UploadFile = File(...),
    _=Depends(get_current_user),
    request: Request = None,
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
    host = request.base_url if request else "http://127.0.0.1:8000/"
    return {"ok": True, "name": file.filename, "url": f"{str(host).rstrip('/')}/uploads/{fname}"}
