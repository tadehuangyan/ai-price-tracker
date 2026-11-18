# -*- coding: utf-8 -*-
"""模拟邮箱（沙箱邮件）路由

类比支付宝沙箱支付：邮件不真实外发（SMTP 端口受限），
而是"模拟投递"落库到 mail_messages，再通过收件箱/沙箱收件箱查看。
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_admin
from ..models import MailMessage, User
from ..schemas import SendCodeIn, VerifyCodeIn
from ..services.mailer import (
    CATEGORY_NAMES,
    check_verification_code,
    mail_to_dict,
    send_verification_code,
)

router = APIRouter(prefix="/api/mail", tags=["模拟邮箱"])


@router.post("/send-code")
def send_code(body: SendCodeIn, db: Session = Depends(get_db)):
    """发送模拟验证码邮件（注册/换绑邮箱/修改密码）"""
    if body.purpose == "register":
        if db.query(User).filter(User.email == body.email).first():
            raise HTTPException(400, "该邮箱已被注册")
    return _do_send_code(body.email, body.purpose, None, db)


@router.post("/send-code-auth")
def send_code_auth(
    body: SendCodeIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """登录态下发送验证码（换绑邮箱/修改密码）"""
    if body.purpose == "register":
        raise HTTPException(400, "注册验证码无需登录，请使用 /api/mail/send-code")
    if body.purpose == "email_change":
        if body.email == user.email:
            raise HTTPException(400, "新邮箱与当前邮箱相同")
        if db.query(User).filter(User.email == body.email).first():
            raise HTTPException(400, "该邮箱已被注册")
    else:  # password_change：验证码发往当前邮箱
        if body.email != user.email:
            raise HTTPException(400, "修改密码验证码只能发送到当前绑定邮箱")
    return _do_send_code(body.email, body.purpose, user.id, db)


def _do_send_code(email: str, purpose: str, user_id, db: Session):
    """统一的发码入口：投递失败时转换为 400 错误抛出"""
    ok, message, _ = send_verification_code(db, email, purpose, user_id)
    if not ok:
        raise HTTPException(400, message)
    return {"ok": True, "message": message}


@router.post("/verify-code")
def verify_code(body: VerifyCodeIn, db: Session = Depends(get_db)):
    """校验验证码（不作废，仅预检；正式作废在注册/换绑/改密时发生）"""
    if not check_verification_code(db, body.email, body.purpose, body.code, consume=False):
        raise HTTPException(400, "验证码错误或已过期")
    return {"ok": True}


@router.get("/sandbox")
def sandbox_inbox(
    email: str = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """沙箱收件箱（免登录）：按邮箱查询模拟投递的邮件，供注册前查看验证码"""
    q = db.query(MailMessage).filter(MailMessage.to_email == email)
    total = q.count()
    rows = q.order_by(MailMessage.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [mail_to_dict(m) for m in rows],
    }


@router.get("/inbox")
def my_inbox(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """我的邮箱（收件箱）"""
    q = db.query(MailMessage).filter(
        (MailMessage.user_id == user.id) | (MailMessage.to_email == user.email)
    )
    total = q.count()
    rows = q.order_by(MailMessage.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "unread": q.filter(MailMessage.is_read == False).count(),  # noqa: E712
        "items": [mail_to_dict(m) for m in rows],
    }


@router.post("/{mail_id}/read")
def mark_read(
    mail_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """标记单封邮件为已读（仅限收件人本人）"""
    m = db.query(MailMessage).get(mail_id)
    if m and (m.user_id == user.id or m.to_email == user.email):
        m.is_read = True
        db.commit()
    return {"ok": True}


@router.post("/read-all")
def mark_all_read(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """一键将当前用户的全部未读邮件标记为已读"""
    db.query(MailMessage).filter(
        ((MailMessage.user_id == user.id) | (MailMessage.to_email == user.email))
        & (MailMessage.is_read == False)  # noqa: E712
    ).update({"is_read": True}, synchronize_session=False)
    db.commit()
    return {"ok": True}


# ---------- 管理端：全站模拟邮件记录 ----------

@router.get("/admin/list")
def admin_list(
    keyword: str = Query(""),
    category: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    """管理端：全站模拟邮件记录查询（按邮箱/主题关键词与分类筛选，分页返回）"""
    q = db.query(MailMessage)
    if keyword:
        q = q.filter(
            (MailMessage.to_email.contains(keyword)) | (MailMessage.subject.contains(keyword))
        )
    if category:
        q = q.filter(MailMessage.category == category)
    total = q.count()
    rows = q.order_by(MailMessage.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [mail_to_dict(m) for m in rows],
        "categories": [{"value": k, "label": v} for k, v in CATEGORY_NAMES.items()],
    }
