from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Listing, PriceSnapshot, Product
from ..schemas import Page, ProductOut, RealtimeCrawlIn
from ..services.crawler import realtime_crawl

router = APIRouter(prefix="/api/products", tags=["商品价格查询"])


def _product_min_price(db: Session, product_id: int) -> float:
    v = (
        db.query(func.min(Listing.current_price))
        .filter(Listing.product_id == product_id)
        .scalar()
    )
    return round(v, 2) if v else None


def _product_out(db: Session, p: Product) -> dict:
    d = ProductOut.model_validate(p).model_dump(mode="json")
    d["min_price"] = _product_min_price(db, p.id)
    d["listings"] = [
        {
            "id": l.id,
            "platform": l.platform,
            "url": l.url,
            "title": l.title,
            "current_price": l.current_price,
            "last_crawled_at": l.last_crawled_at.isoformat() if l.last_crawled_at else None,
        }
        for l in p.listings
    ]
    return d


@router.get("/search")
def search(
    keyword: str = Query("", max_length=100),
    category: str = Query(""),
    sort: str = Query("random"),  # random / default / price_asc / price_desc / newest
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """REQ-SPT-201 商品搜索：关键词检索、分页、排序（random 每次随机展示）"""
    q = db.query(Product)
    if keyword:
        q = q.filter(Product.name.contains(keyword))
    if category:
        q = q.filter(Product.category == category)
    total = q.count()

    if sort == "random":
        q = q.order_by(func.rand())
    elif sort == "newest":
        q = q.order_by(Product.id.desc())
    elif sort in ("price_asc", "price_desc"):
        min_price = func.min(Listing.current_price).label("mp")
        q = (
            db.query(Product, min_price)
            .outerjoin(Listing, Listing.product_id == Product.id)
            .group_by(Product.id)
        )
        if keyword:
            q = q.filter(Product.name.contains(keyword))
        if category:
            q = q.filter(Product.category == category)
        q = q.order_by(min_price.asc() if sort == "price_asc" else min_price.desc())
        rows = q.offset((page - 1) * page_size).limit(page_size).all()
        items = [_product_out(db, r[0]) for r in rows]
        return Page(total=total, page=page, page_size=page_size, items=items)

    rows = q.offset((page - 1) * page_size).limit(page_size).all()
    items = [_product_out(db, p) for p in rows]
    return Page(total=total, page=page, page_size=page_size, items=items)


@router.get("/categories")
def categories(db: Session = Depends(get_db)):
    rows = (
        db.query(Product.category, func.count(Product.id))
        .filter(Product.category != "")
        .group_by(Product.category)
        .all()
    )
    return [{"category": c, "count": n} for c, n in rows]


# ---------- 全网新发现：展示数据库之外的商品 ----------

DISCOVER_KEYWORDS = [
    "手机", "机械键盘", "蓝牙耳机", "扫地机器人", "路由器", "显示器",
    "充电宝", "吹风机", "平板电脑", "笔记本电脑", "智能手表", "电动牙刷",
    "投影仪", "微波炉", "游戏手柄", "音箱",
]

_discover_cache = {"at": 0.0, "items": []}
DISCOVER_CACHE_TTL = 600  # 10 分钟


@router.get("/discover")
def discover(
    n: int = Query(8, ge=1, le=20),
    refresh: int = Query(0),
    db: Session = Depends(get_db),
):
    """从慢慢买实时发现数据库之外的全网商品（带 10 分钟缓存，refresh=1 强制换一批）"""
    import random
    import time

    if (
        not refresh
        and time.time() - _discover_cache["at"] < DISCOVER_CACHE_TTL
        and _discover_cache["items"]
    ):
        items = _discover_cache["items"][:n]
    else:
        from ..services.crawler.manmanbuy import discover_products

        keyword = random.choice(DISCOVER_KEYWORDS)
        found = discover_products(keyword, limit=n + 12)
        # 过滤已在库的商品
        known = {u for (u,) in db.query(Listing.url).all()}
        items = []
        for f in found:
            if f["url"] in known:
                continue
            items.append(
                {
                    "title": f["title"],
                    "price": f["price"],
                    "platform": f["platform"],
                    "url": f["url"],
                    "image": f["image"],
                    "keyword": f["keyword"],
                }
            )
            if len(items) >= 20:
                break
        _discover_cache["at"] = time.time()
        _discover_cache["items"] = items
        items = items[:n]
    return {"keyword": _discover_cache.get("keyword", ""), "items": items}


class ImportIn(BaseModel):
    url: str = Field(min_length=8, max_length=500)
    title: str = Field(default="", max_length=255)
    price: float | None = None
    category: str = ""


@router.post("/import")
def import_product(body: ImportIn, db: Session = Depends(get_db)):
    """把发现的新商品收录入库：创建商品与报价，并同步查询历史价格"""
    if not body.url.startswith(("http://", "https://")):
        raise HTTPException(400, "商品链接不合法")
    existing = db.query(Listing).filter(Listing.url == body.url).first()
    if existing:
        return {"ok": True, "product_id": existing.product_id, "message": "商品已在库中"}

    title = body.title
    image = ""
    history = []
    price = body.price or 0
    platform = "taobao"
    crawl_err = ""
    try:
        from ..services.crawler.manmanbuy import query_history

        data = query_history(body.url, timeout_ms=25000)
        title = title or data["title"]
        image = data["image_url"]
        history = data["history"]
        price = data["price"] or price
        platform = data["platform"] or platform
    except Exception as e:
        crawl_err = str(e)[:200]

    if not title:
        raise HTTPException(502, f"收录失败：未能获取商品标题（{crawl_err}）")

    product = Product(name=title, category=body.category, image_url=image)
    db.add(product)
    db.flush()
    listing = Listing(
        product_id=product.id,
        platform=platform,
        url=body.url,
        title=title,
        current_price=round(price, 2) if price else None,
        last_crawled_at=datetime.now(),
    )
    db.add(listing)
    db.flush()
    points = 0
    for date_str, p in history:
        snap_time = datetime.strptime(date_str + " 12:00:00", "%Y-%m-%d %H:%M:%S")
        db.add(PriceSnapshot(listing_id=listing.id, price=p, captured_at=snap_time))
        points += 1
    db.commit()
    # 从发现缓存中移除
    _discover_cache["items"] = [i for i in _discover_cache["items"] if i["url"] != body.url]
    return {
        "ok": True,
        "product_id": product.id,
        "message": f"收录成功，历史价格 {points} 天" + (f"（历史查询：{crawl_err}）" if crawl_err else ""),
    }


@router.get("/{product_id}")
def detail(product_id: int, db: Session = Depends(get_db)):
    """REQ-SPT-202 商品详情 + 最新价格快照"""
    p = db.query(Product).get(product_id)
    if p is None:
        raise HTTPException(404, "商品不存在")
    d = _product_out(db, p)

    # 每个报价的最近若干条快照
    for item, l in zip(d["listings"], p.listings):
        snaps = (
            db.query(PriceSnapshot)
            .filter(PriceSnapshot.listing_id == l.id)
            .order_by(PriceSnapshot.captured_at.desc())
            .limit(10)
            .all()
        )
        item["recent_snapshots"] = [
            {"date": s.captured_at.strftime("%Y-%m-%d"), "price": s.price} for s in reversed(snaps)
        ]
    return d


@router.post("/realtime")
def realtime(body: RealtimeCrawlIn, db: Session = Depends(get_db)):
    """REQ-SPT-203 实时价格查询：对未入库商品链接即时采集一次"""
    if not body.url.startswith(("http://", "https://")):
        raise HTTPException(400, "请输入合法的商品链接（http/https）")
    try:
        result = realtime_crawl(body.url)
    except Exception as e:
        raise HTTPException(502, f"采集失败：{e}")
    if result is None:
        raise HTTPException(502, "采集失败：未能从页面解析出价格，请检查链接是否为商品详情页")
    return {
        "platform": result["platform"],
        "title": result.get("title", ""),
        "price": result["price"],
        "image_url": result.get("image_url", ""),
        "captured_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
