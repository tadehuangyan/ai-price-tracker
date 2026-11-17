from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Alert, Listing, PriceSnapshot, Product, Tracking, User
from ..schemas import TrackingIn

router = APIRouter(prefix="/api/tracking", tags=["价格追踪"])

MAX_TRACK_PER_USER = 30  # REQ-SPT-305 每用户追踪上限


def _product_current_price(db: Session, product_id: int):
    v = (
        db.query(func.min(Listing.current_price))
        .filter(Listing.product_id == product_id)
        .scalar()
    )
    return round(v, 2) if v else None


@router.post("")
def add_tracking(
    body: TrackingIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """REQ-SPT-301 添加追踪并设置目标价格"""
    product = db.query(Product).get(body.product_id)
    if product is None:
        raise HTTPException(404, "商品不存在")
    exists = (
        db.query(Tracking)
        .filter(Tracking.user_id == user.id, Tracking.product_id == body.product_id)
        .first()
    )
    if exists:
        if body.target_price is not None:
            exists.target_price = body.target_price
            db.commit()
        return {"ok": True, "message": "该商品已在追踪中，目标价已更新"}
    count = db.query(Tracking).filter(Tracking.user_id == user.id).count()
    if count >= MAX_TRACK_PER_USER:
        raise HTTPException(400, f"追踪商品数量已达上限（{MAX_TRACK_PER_USER} 个）")
    if body.target_price is not None and body.target_price <= 0:
        raise HTTPException(400, "目标价格须大于 0")
    db.add(
        Tracking(user_id=user.id, product_id=body.product_id, target_price=body.target_price)
    )
    db.commit()
    return {"ok": True, "message": "已加入价格追踪"}


@router.get("")
def list_trackings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(Tracking, Product)
        .join(Product, Tracking.product_id == Product.id)
        .filter(Tracking.user_id == user.id)
        .order_by(Tracking.created_at.desc())
        .all()
    )
    return [
        {
            "id": t.id,
            "product_id": t.product_id,
            "product_name": p.name,
            "image_url": p.image_url,
            "target_price": t.target_price,
            "current_price": _product_current_price(db, t.product_id),
            "created_at": t.created_at.strftime("%Y-%m-%d %H:%M") if t.created_at else None,
        }
        for t, p in rows
    ]


@router.delete("/{tracking_id}")
def remove_tracking(
    tracking_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    t = db.query(Tracking).get(tracking_id)
    if t is None:
        raise HTTPException(404, "追踪记录不存在")
    if t.user_id != user.id and user.role != "admin":
        raise HTTPException(403, "无权操作他人追踪记录")
    db.delete(t)
    db.commit()
    return {"ok": True}


@router.get("/trend/{product_id}")
def trend(
    product_id: int,
    days: int = Query(180, ge=7, le=730),
    platform: str = Query(""),
    db: Session = Depends(get_db),
):
    """REQ-SPT-303 价格走势：按天取当日最低价，标注最高/最低/当前价"""
    product = db.query(Product).get(product_id)
    if product is None:
        raise HTTPException(404, "商品不存在")

    since = datetime.now() - timedelta(days=days)
    q = (
        db.query(PriceSnapshot, Listing.platform)
        .join(Listing, PriceSnapshot.listing_id == Listing.id)
        .filter(Listing.product_id == product_id, PriceSnapshot.captured_at >= since)
    )
    if platform:
        q = q.filter(Listing.platform == platform)
    rows = q.order_by(PriceSnapshot.captured_at.asc()).all()

    daily = {}  # date -> (min_price, platform)
    for snap, plat in rows:
        d = snap.captured_at.strftime("%Y-%m-%d")
        if d not in daily or snap.price < daily[d][0]:
            daily[d] = (snap.price, plat)

    points = [
        {"date": d, "price": round(v[0], 2), "platform": v[1]} for d, v in sorted(daily.items())
    ]
    prices = [p["price"] for p in points]
    current = _product_current_price(db, product_id)
    return {
        "product_id": product_id,
        "product_name": product.name,
        "days": days,
        "points": points,
        "min_price": min(prices) if prices else None,
        "max_price": max(prices) if prices else None,
        "current_price": current,
        "avg_price": round(sum(prices) / len(prices), 2) if prices else None,
    }


@router.get("/alerts")
def my_alerts(
    unread_only: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """REQ-SPT-304 降价提醒（站内消息）"""
    q = db.query(Alert).filter(Alert.user_id == user.id)
    if unread_only:
        q = q.filter(Alert.is_read == False)  # noqa: E712
    rows = q.order_by(Alert.created_at.desc()).limit(100).all()
    return [
        {
            "id": a.id,
            "product_id": a.product_id,
            "product_name": a.product.name if a.product else "",
            "price": a.price,
            "target_price": a.target_price,
            "message": a.message,
            "is_read": a.is_read,
            "created_at": a.created_at.strftime("%Y-%m-%d %H:%M") if a.created_at else None,
        }
        for a in rows
    ]


@router.post("/alerts/{alert_id}/read")
def mark_read(
    alert_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    a = db.query(Alert).get(alert_id)
    if a and a.user_id == user.id:
        a.is_read = True
        db.commit()
    return {"ok": True}


@router.post("/alerts/read-all")
def mark_all_read(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(Alert).filter(Alert.user_id == user.id, Alert.is_read == False).update(  # noqa: E712
        {"is_read": True}
    )
    db.commit()
    return {"ok": True}
