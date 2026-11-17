from datetime import datetime

import threading

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
    """商品查询页分类索引：与慢慢买站内分类保持一致（一级分类）"""
    from ..services.crawler.manmanbuy import MANMANBUY_CATEGORIES

    return MANMANBUY_CATEGORIES


# ---------- 实时数据：全部商品信息均通过慢慢买获取 ----------

_live_cache: dict = {}  # (keyword, category) -> (ts, items)
LIVE_CACHE_TTL = 300  # 5 分钟

# stale-while-revalidate：缓存过期时先回旧数据、后台静默刷新，用户无需等待爬虫
_refreshing: set = set()
_refresh_lock = threading.Lock()


def _mark_refreshing(key) -> bool:
    with _refresh_lock:
        if key in _refreshing:
            return False
        _refreshing.add(key)
        return True


def _done_refreshing(key) -> None:
    with _refresh_lock:
        _refreshing.discard(key)


def _fetch_live_items(keyword: str, category: str, n: int) -> list:
    """实时抓取商品列表（同步爬取，缓存填充与后台刷新共用）"""
    if keyword.strip():
        from ..services.crawler.manmanbuy import discover_products

        items = discover_products(keyword.strip(), limit=n)
        for i in items:
            i["kind"] = "product"
    else:
        from ..services.crawler.manmanbuy import browse_category

        items = browse_category(category.strip(), limit=n)
    return items


@router.get("/live-search")
def live_search(
    keyword: str = Query("", max_length=100),
    category: str = Query("", max_length=20),
    n: int = Query(24, ge=1, le=60),
    refresh: int = Query(0),
):
    """实时从慢慢买获取商品列表：关键词走比价搜索，分类/默认走全网折扣分类页

    缓存 5 分钟；过期后先返回上一批数据并后台刷新，避免用户等待爬虫。
    """
    import time

    key = (keyword.strip(), category.strip())
    cached = _live_cache.get(key)
    if not refresh and cached:
        if time.time() - cached[0] < LIVE_CACHE_TTL:
            return {"keyword": keyword, "category": category, "items": cached[1][:n]}
        if _mark_refreshing(key):
            def _bg():
                try:
                    _live_cache[key] = (time.time(), _fetch_live_items(keyword, category, n))
                except Exception:
                    pass
                finally:
                    _done_refreshing(key)
            threading.Thread(target=_bg, daemon=True).start()
        return {"keyword": keyword, "category": category, "items": cached[1][:n]}

    items = _fetch_live_items(keyword, category, n)
    _live_cache[key] = (time.time(), items)
    return {"keyword": keyword, "category": category, "items": items}


@router.get("/live")
def live(url: str = Query("", max_length=500)):
    """实时商品详情（慢慢买历史价格），不写库；爆料链接自动解析出原始商品链接"""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "商品链接不合法")
    try:
        from ..services.crawler.manmanbuy import live_product

        data = live_product(url)
    except Exception as e:
        raise HTTPException(502, f"慢慢买实时查询失败：{e}")

    history = data.get("history") or []
    prices = [p for _, p in history]
    return {
        "title": data.get("title", ""),
        "image_url": data.get("image_url", ""),
        "price": data.get("price"),
        "platform": data.get("platform", ""),
        "site_name": data.get("site_name", ""),
        "product_url": data.get("product_url", url),
        "deal_url": data.get("deal_url", ""),
        "history": history,
        "min_price": min(prices) if prices else None,
        "max_price": max(prices) if prices else None,
        "avg_price": round(sum(prices) / len(prices), 2) if prices else None,
        "current_price": data.get("price"),
        "history_min": data.get("history_min"),
        "history_min_date": data.get("history_min_date"),
    }


# ---------- 全网新发现：展示数据库之外的商品 ----------

DISCOVER_KEYWORDS = [
    "手机", "机械键盘", "蓝牙耳机", "扫地机器人", "路由器", "显示器",
    "充电宝", "吹风机", "平板电脑", "笔记本电脑", "智能手表", "电动牙刷",
    "投影仪", "微波炉", "游戏手柄", "音箱",
]

_discover_cache = {"at": 0.0, "items": []}
DISCOVER_CACHE_TTL = 600  # 10 分钟


def _fetch_discover_items(db: Session, n: int) -> list:
    """实时发现一批库外商品（同步爬取）"""
    import random

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
    return items


@router.get("/discover")
def discover(
    n: int = Query(8, ge=1, le=20),
    refresh: int = Query(0),
    db: Session = Depends(get_db),
):
    """从慢慢买实时发现数据库之外的全网商品（带 10 分钟缓存，refresh=1 强制换一批）

    缓存过期后先返回上一批数据并后台刷新，避免用户等待爬虫。
    """
    import time

    if (
        not refresh
        and time.time() - _discover_cache["at"] < DISCOVER_CACHE_TTL
        and _discover_cache["items"]
    ):
        items = _discover_cache["items"][:n]
    elif not refresh and _discover_cache["items"]:
        # 过期但有旧数据：先回旧的，后台静默换新
        if _mark_refreshing("discover"):
            def _bg():
                from ..database import SessionLocal

                s = SessionLocal()
                try:
                    fresh = _fetch_discover_items(s, n)
                    _discover_cache["at"] = time.time()
                    _discover_cache["items"] = fresh
                except Exception:
                    pass
                finally:
                    s.close()
                    _done_refreshing("discover")
            threading.Thread(target=_bg, daemon=True).start()
        items = _discover_cache["items"][:n]
    else:
        items = _fetch_discover_items(db, n)
        _discover_cache["at"] = time.time()
        _discover_cache["items"] = items
        items = items[:n]
    return {"keyword": _discover_cache.get("keyword", ""), "items": items}


class HistoryPoint(BaseModel):
    date: str = Field(max_length=10)
    price: float


class ImportIn(BaseModel):
    url: str = Field(min_length=8, max_length=500)
    title: str = Field(default="", max_length=255)
    price: float | None = None
    category: str = ""
    image: str = Field(default="", max_length=500)
    platform: str = Field(default="", max_length=20)
    history: list[HistoryPoint] = Field(default_factory=list)


@router.post("/import")
def import_product(body: ImportIn, db: Session = Depends(get_db)):
    """把商品收录入库：创建商品与报价，并写入历史价格

    带 history（实时查询结果）时直接落库，否则回退为实时查询慢慢买。
    """
    if not body.url.startswith(("http://", "https://")):
        raise HTTPException(400, "商品链接不合法")
    existing = db.query(Listing).filter(Listing.url == body.url).first()
    if existing:
        return {"ok": True, "product_id": existing.product_id, "message": "商品已在库中"}

    title = body.title
    image = body.image
    history = [(h.date, h.price) for h in body.history]
    price = body.price or 0
    platform = body.platform or "taobao"
    crawl_err = ""
    if not history:
        try:
            from ..services.crawler.manmanbuy import live_product

            data = live_product(body.url, timeout_ms=25000)
            title = title or data["title"]
            image = image or data["image_url"]
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
