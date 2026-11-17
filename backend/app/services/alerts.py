# -*- coding: utf-8 -*-
"""降价提醒（REQ-SPT-304）：站内消息"""
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Alert, Listing, Product, Tracking, User
from .mailer import send_mail


def check_price_alerts(db: Session) -> int:
    """对所有追踪订阅比对目标价，达标则产生站内消息（当天不重复）"""
    rows = (
        db.query(Tracking, Product, User)
        .join(Product, Tracking.product_id == Product.id)
        .join(User, Tracking.user_id == User.id)
        .filter(Tracking.target_price.isnot(None))
        .all()
    )
    created = 0
    today = datetime.now().date()
    for tracking, product, user in rows:
        price = (
            db.query(func.min(Listing.current_price))
            .filter(Listing.product_id == product.id)
            .scalar()
        )
        if price is None or price > tracking.target_price:
            continue
        already = (
            db.query(Alert)
            .filter(
                Alert.user_id == user.id,
                Alert.product_id == product.id,
                func.date(Alert.created_at) == today,
            )
            .first()
        )
        if already:
            continue
        msg = (
            f"降价提醒：「{product.name}」当前价 {price:.2f} 元，"
            f"已达到你设置的目标价 {tracking.target_price:.2f} 元"
        )
        db.add(
            Alert(
                user_id=user.id,
                product_id=product.id,
                price=price,
                target_price=tracking.target_price,
                message=msg,
            )
        )
        send_mail(  # 模拟邮箱：同步投递降价提醒邮件
            db,
            to_email=user.email,
            user_id=user.id,
            category="price_alert",
            subject="【模拟邮箱】降价提醒",
            body=(
                f"{msg}\n\n当前最低价：{price:.2f} 元\n"
                f"你的目标价：{tracking.target_price:.2f} 元\n"
                f"（本邮件由模拟邮箱沙箱投递，不会真实发送）"
            ),
        )
        created += 1
    if created:
        db.commit()
    return created
