# -*- coding: utf-8 -*-
"""模拟邮箱（沙箱邮件）服务

与支付宝沙箱支付同思路：由于 SMTP 端口受限，邮件不真实外发，
仅写入 mail_messages 表模拟"投递成功"，用户在「我的邮箱」、
管理员在「邮件记录」中可像真实邮箱一样查看。
"""
import random
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from ..models import MailMessage

CODE_TTL_SECONDS = 600         # 验证码有效期：10 分钟
RESEND_INTERVAL_SECONDS = 60   # 同邮箱同用途验证码重发间隔

CATEGORY_NAMES = {
    "verify_code": "验证码",
    "price_alert": "降价提醒",
    "subscribe": "订阅确认",
    "system": "系统通知",
}

PURPOSE_NAMES = {
    "register": "注册账号",
    "email_change": "修改邮箱",
    "password_change": "修改密码",
}


def send_mail(
    db: Session,
    *,
    to_email: str,
    subject: str,
    body: str,
    category: str = "system",
    user_id: int = None,
    purpose: str = "",
    code: str = "",
) -> MailMessage:
    """模拟发送一封邮件（不真实外发，仅落库），由调用方负责 commit"""
    mail = MailMessage(
        user_id=user_id,
        to_email=to_email,
        category=category,
        purpose=purpose,
        subject=subject,
        body=body,
        code=code,
        status="sent",
    )
    db.add(mail)
    return mail


def send_verification_code(db: Session, email: str, purpose: str, user_id: int = None):
    """生成 6 位验证码并模拟投递。返回 (ok, message, code)"""
    # 频率限制：同邮箱同用途 60 秒内只允许重发一次（查最近一条发送记录）
    last = (
        db.query(MailMessage)
        .filter(
            MailMessage.to_email == email,
            MailMessage.category == "verify_code",
            MailMessage.purpose == purpose,
        )
        .order_by(MailMessage.created_at.desc())
        .first()
    )
    if last and last.created_at and (datetime.now() - last.created_at).total_seconds() < RESEND_INTERVAL_SECONDS:
        return False, "发送过于频繁，请 60 秒后再试", ""

    code = f"{random.randint(0, 999999):06d}"  # 6 位数字验证码（左补零）
    name = PURPOSE_NAMES.get(purpose, purpose)
    send_mail(
        db,
        to_email=email,
        user_id=user_id,
        category="verify_code",
        purpose=purpose,
        code=code,
        subject=f"【模拟邮箱】{name}验证码",
        body=(
            f"你正在进行「{name}」操作，验证码为 {code}，"
            f"{CODE_TTL_SECONDS // 60} 分钟内有效。\n"
            f"（本邮件由模拟邮箱沙箱投递，不会真实发送到你的邮箱）"
        ),
    )
    db.commit()
    return True, "验证码已模拟投递，请在模拟收件箱查看", code


def check_verification_code(db: Session, email: str, purpose: str, code: str, consume: bool = True) -> bool:
    """校验验证码：最新一条匹配、未使用、在有效期内则通过；consume=True 时作废（由调用方 commit）"""
    if not code:
        return False
    # 有效期内的匹配记录：邮箱 + 用途 + 验证码 + 未使用，取最新一条
    since = datetime.now() - timedelta(seconds=CODE_TTL_SECONDS)
    mail = (
        db.query(MailMessage)
        .filter(
            MailMessage.to_email == email,
            MailMessage.category == "verify_code",
            MailMessage.purpose == purpose,
            MailMessage.code == code,
            MailMessage.code_used == False,  # noqa: E712
            MailMessage.created_at >= since,
        )
        .order_by(MailMessage.created_at.desc())
        .first()
    )
    if mail is None:
        return False
    if consume:
        mail.code_used = True
    return True


def mail_to_dict(m: MailMessage) -> dict:
    """邮件记录 -> API/前端展示用 dict（含分类中文名、验证码使用状态）"""
    return {
        "id": m.id,
        "to_email": m.to_email,
        "category": m.category,
        "category_name": CATEGORY_NAMES.get(m.category, m.category),
        "purpose": m.purpose,
        "subject": m.subject,
        "body": m.body,
        "code": m.code,
        "code_used": m.code_used,
        "is_read": m.is_read,
        "status": m.status,
        "created_at": m.created_at.strftime("%Y-%m-%d %H:%M:%S") if m.created_at else None,
    }
