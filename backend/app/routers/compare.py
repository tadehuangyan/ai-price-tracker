"""价格对比路由：多商品（<=5）跨平台报价对比与历史价格走势对比"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Listing, PriceSnapshot, Product
from ..schemas import CompareIn

router = APIRouter(prefix="/api/compare", tags=["价格对比"])


def _daily_series(db: Session, product_id: int, days: int):
    """聚合商品近 N 天的每日最低价序列，返回 {日期: (价格, 平台)}"""
    since = datetime.now() - timedelta(days=days)
    rows = (
        db.query(PriceSnapshot, Listing.platform)
        .join(Listing, PriceSnapshot.listing_id == Listing.id)
        .filter(Listing.product_id == product_id, PriceSnapshot.captured_at >= since)
        .order_by(PriceSnapshot.captured_at.asc())
        .all()
    )
    daily = {}
    # 同一天多个快照只保留最低价（及其来源平台）
    for snap, plat in rows:
        d = snap.captured_at.strftime("%Y-%m-%d")
        if d not in daily or snap.price < daily[d][0]:
            daily[d] = (snap.price, plat)
    return daily


@router.post("")
def compare(body: CompareIn, db: Session = Depends(get_db)):
    """REQ-SPT-401/402/403 多商品（<=5）多平台比价 + 历史价格对比"""
    if len(body.product_ids) > 5:
        raise HTTPException(400, "单次对比商品数量上限为 5 个")
    if len(set(body.product_ids)) != len(body.product_ids):
        raise HTTPException(400, "对比商品不能重复")

    products = db.query(Product).filter(Product.id.in_(body.product_ids)).all()
    found_ids = {p.id for p in products}
    missing = [i for i in body.product_ids if i not in found_ids]
    if missing:
        raise HTTPException(404, f"商品不存在：{missing}")

    result = []
    for p in products:
        listings = db.query(Listing).filter(Listing.product_id == p.id).all()
        offers = [
            {
                "platform": l.platform,
                "title": l.title or p.name,
                "price": l.current_price,
                "url": l.url,
            }
            for l in listings
            if l.current_price
        ]
        offers.sort(key=lambda x: x["price"])
        lowest = offers[0] if offers else None

        daily = _daily_series(db, p.id, body.days)
        prices = [v[0] for v in daily.values()]
        result.append(
            {
                "product_id": p.id,
                "product_name": p.name,
                "image_url": p.image_url,
                "offers": offers,
                "lowest": lowest,
                # 各平台当前报价的最高与最低价差（仅一个报价时为 0）
                "diff": round(offers[-1]["price"] - offers[0]["price"], 2)
                if len(offers) > 1
                else 0,
                "history_min": round(min(prices), 2) if prices else None,
                "history_max": round(max(prices), 2) if prices else None,
                "current_min": lowest["price"] if lowest else None,
                "series": [
                    {"date": d, "price": round(v[0], 2)}
                    for d, v in sorted(daily.items())
                ],
            }
        )

    # 同款跨平台当前价汇总（REQ-SPT-401）
    all_platforms = sorted({o["platform"] for r in result for o in r["offers"]})
    return {
        "days": body.days,
        "products": result,
        "platforms": all_platforms,
    }
