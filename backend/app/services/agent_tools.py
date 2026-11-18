# -*- coding: utf-8 -*-
"""Agent 工具层（Function Calling）：把商品查询/比价/价格追踪能力封装为大模型可调用的工具

- TOOL_SPECS：OpenAI 兼容 tools 参数的函数定义
- dispatch()：白名单分发执行，未知工具/参数错误均返回错误文本（供模型自行解释），
  不抛异常、不执行任意代码；写操作（set_price_alert）需登录用户。
"""
import json

from sqlalchemy.orm import Session

from ..models import Listing, Product, Tracking, User

MAX_TRACK_PER_USER = 30  # 与 routers/tracking.py 的追踪上限一致

TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": "get_price_history",
            "description": "查询商品的历史价格与当前多平台报价。product_id（系统内商品）与 url（商品链接）二选一。",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "integer", "description": "系统内商品 ID"},
                    "url": {"type": "string", "description": "商品链接（京东/淘宝等）"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "按关键词搜索系统内已收录的商品，返回候选商品列表（含 ID 与最低报价）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "商品关键词"},
                    "limit": {"type": "integer", "description": "返回条数上限，默认 5"},
                },
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_products",
            "description": "对比多个商品的历史价格与当前最低价，用于回答『哪个更划算』类问题。",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "要对比的商品 ID 列表（2-5 个）",
                    },
                    "days": {"type": "integer", "description": "历史统计天数，默认 30"},
                },
                "required": ["product_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_price_alert",
            "description": "为用户创建/更新价格追踪并设置目标价，达到目标价时系统推送降价提醒。执行前需明确用户已确认商品与目标价。",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "integer", "description": "系统内商品 ID"},
                    "target_price": {"type": "number", "description": "目标价格（元）"},
                },
                "required": ["product_id", "target_price"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_trackings",
            "description": "查询当前用户正在追踪的商品及目标价。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_knowledge",
            "description": "检索比价攻略/大促规律/品类选购指南知识库，回答选购技巧、大促时间点、比价方法类问题时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "要检索的问题或关键词"},
                },
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_user_profile",
            "description": "将对话中了解到的用户消费偏好/预算/关注商品/购买习惯记录到用户画像文件，用于后续个性化建议。每条只记一个事实，简洁。",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "类别：偏好（消费偏好）/ 预算（预算区间）/ 关注（关注商品）/ 习惯（购买习惯）",
                    },
                    "note": {"type": "string", "description": "不超过 50 字的事实描述，如：预算约 3000 元、偏好性价比高的手机"},
                },
                "required": ["category", "note"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_profile",
            "description": "读取当前用户画像（已记录的消费偏好/预算/关注/习惯），需要个性化建议前可先查询。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "（MCP）按关键词搜索网页，了解商品行情、市场动态、促销资讯，用于判断行情后给出更合理的消费建议。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词，如：RTX4060 行情、618 手机降价"},
                    "limit": {"type": "integer", "description": "返回条数上限，默认 5"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_webpage",
            "description": "（MCP）抓取指定网页正文，深入了解行情资讯/评测/促销规则后再给出消费建议。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "网页链接（http/https）"},
                },
                "required": ["url"],
            },
        },
    },
]

# 前端工具卡片展示名
TOOL_LABELS = {
    "get_price_history": "查询历史价格",
    "search_products": "搜索商品",
    "compare_products": "多品比价",
    "set_price_alert": "创建价格提醒",
    "list_trackings": "查看追踪列表",
    "query_knowledge": "检索知识库",
    "update_user_profile": "记录用户偏好",
    "get_user_profile": "读取用户画像",
    "web_search": "搜索行情资讯",
    "fetch_webpage": "获取网页行情",
}


def _j(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def _to_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _get_price_history(db: Session, user, args: dict) -> str:
    from .ai_advisor import _link_brief, build_context  # 延迟导入避免循环依赖

    pid = _to_int(args.get("product_id"))
    url = str(args.get("url") or "").strip()
    if pid is not None:
        try:
            ctx = build_context(db, pid)
        except ValueError:
            return _j({"error": f"商品 {pid} 不存在"})
        return _j(ctx)
    if url:
        try:
            from .crawler.manmanbuy import query_history

            return _j(query_history(url, timeout_ms=30000))
        except Exception as e:
            return _j({"error": f"链接抓取失败：{e}"})
    return _j({"error": "需要提供 product_id 或 url"})


def _search_products(db: Session, user, args: dict) -> str:
    keyword = str(args.get("keyword") or "").strip()
    limit = min(_to_int(args.get("limit")) or 5, 10)
    if not keyword:
        return _j({"error": "缺少 keyword"})
    rows = db.query(Product).filter(Product.name.like(f"%{keyword}%")).limit(limit).all()
    results = []
    for p in rows:
        prices = [l.current_price for l in p.listings if l.current_price]
        results.append({
            "product_id": p.id,
            "name": p.name,
            "category": p.category,
            "min_price": min(prices) if prices else None,
            "offer_count": len(prices),
        })
    return _j({"keyword": keyword, "results": results, "source": "系统商品库"})


def _compare_products(db: Session, user, args: dict) -> str:
    from datetime import datetime, timedelta

    from ..models import PriceSnapshot

    ids = args.get("product_ids") or []
    ids = [_to_int(i) for i in ids if _to_int(i) is not None][:5]
    if len(ids) < 2:
        return _j({"error": "需要至少 2 个商品 ID 进行对比"})
    days = min(_to_int(args.get("days")) or 30, 365)
    since = datetime.now() - timedelta(days=days)
    items = []
    for pid in ids:
        p = db.query(Product).get(pid)
        if p is None:
            items.append({"product_id": pid, "error": "商品不存在"})
            continue
        prices = [
            s.price
            for s in db.query(PriceSnapshot)
            .join(Listing, PriceSnapshot.listing_id == Listing.id)
            .filter(Listing.product_id == pid, PriceSnapshot.captured_at >= since)
            .all()
        ]
        offers = sorted(
            ({"platform": l.platform, "price": l.current_price} for l in p.listings if l.current_price),
            key=lambda x: x["price"],
        )
        items.append({
            "product_id": pid,
            "name": p.name,
            "current_min": offers[0]["price"] if offers else None,
            "offers": offers[:5],
            "history_min": round(min(prices), 2) if prices else None,
            "history_avg": round(sum(prices) / len(prices), 2) if prices else None,
            "days": days,
        })
    return _j({"products": items})


def _set_price_alert(db: Session, user, args: dict) -> str:
    if user is None:
        return _j({"ok": False, "error": "需要登录用户才能创建价格追踪"})
    pid = _to_int(args.get("product_id"))
    target = _to_float(args.get("target_price"))
    if pid is None or target is None or target <= 0:
        return _j({"ok": False, "error": "参数不合法：product_id 为整数、target_price 为大于 0 的数字"})
    p = db.query(Product).get(pid)
    if p is None:
        return _j({"ok": False, "error": f"商品 {pid} 不存在"})
    t = db.query(Tracking).filter(Tracking.user_id == user.id, Tracking.product_id == pid).first()
    if t is not None:
        t.target_price = target
        db.commit()
        return _j({"ok": True, "message": f"已更新「{p.name}」的目标价为 {target:.2f} 元", "product_id": pid})
    count = db.query(Tracking).filter(Tracking.user_id == user.id).count()
    if count >= MAX_TRACK_PER_USER:
        return _j({"ok": False, "error": f"追踪商品数量已达上限（{MAX_TRACK_PER_USER} 个）"})
    db.add(Tracking(user_id=user.id, product_id=pid, target_price=target))
    db.commit()
    return _j({
        "ok": True,
        "message": f"已为「{p.name}」创建价格追踪，目标价 {target:.2f} 元，达到目标价将推送降价提醒",
        "product_id": pid,
    })


def _list_trackings(db: Session, user, args: dict) -> str:
    if user is None:
        return _j({"ok": False, "error": "需要登录用户才能查看追踪列表"})
    rows = (
        db.query(Tracking, Product)
        .join(Product, Tracking.product_id == Product.id)
        .filter(Tracking.user_id == user.id)
        .all()
    )
    return _j({
        "trackings": [
            {
                "product_id": p.id,
                "name": p.name,
                "target_price": t.target_price,
                "current_min": min(
                    [l.current_price for l in p.listings if l.current_price], default=None
                ),
            }
            for t, p in rows
        ]
    })


def _query_knowledge(db: Session, user, args: dict) -> str:
    from .knowledge import retrieve

    question = str(args.get("question") or "").strip()
    if not question:
        return _j({"error": "缺少 question"})
    _ctxs, sources = retrieve(db, question, limit=3)
    return _j({"question": question, "items": sources})


def _update_user_profile(db: Session, user, args: dict) -> str:
    from . import user_profile

    if user is None:
        return _j({"ok": False, "error": "需要登录用户才能记录画像"})
    result = user_profile.record_note(user.id, args.get("category"), args.get("note"))
    return _j(result)


def _get_user_profile(db: Session, user, args: dict) -> str:
    from . import user_profile

    if user is None:
        return _j({"ok": False, "error": "需要登录用户才能读取画像"})
    text = user_profile.build_context(user.id)
    return _j({"ok": True, "profile": text or "（暂无画像记录）"})


def _mcp_call(name: str, args: dict) -> str:
    """经 MCP 客户端调用网页工具，失败回填错误文本（由模型向用户解释）"""
    from .mcp_client import McpError, call_tool

    try:
        text = call_tool(name, args)
    except McpError as e:
        return _j({"error": f"MCP 工具调用失败：{e}"})
    except Exception as e:
        return _j({"error": f"MCP 通道异常：{e}"})
    return _j({"ok": True, "content": text[:4000]})


def _web_search(db: Session, user, args: dict) -> str:
    query = str(args.get("query") or "").strip()
    if not query:
        return _j({"error": "缺少 query"})
    return _mcp_call("web_search", {"query": query, "limit": args.get("limit") or 5})


def _fetch_webpage(db: Session, user, args: dict) -> str:
    url = str(args.get("url") or "").strip()
    if not url:
        return _j({"error": "缺少 url"})
    return _mcp_call("fetch_webpage", {"url": url})


HANDLERS = {
    "get_price_history": _get_price_history,
    "search_products": _search_products,
    "compare_products": _compare_products,
    "set_price_alert": _set_price_alert,
    "list_trackings": _list_trackings,
    "query_knowledge": _query_knowledge,
    "update_user_profile": _update_user_profile,
    "get_user_profile": _get_user_profile,
    "web_search": _web_search,
    "fetch_webpage": _fetch_webpage,
}


def dispatch(db: Session, user: User | None, name: str, arguments: str) -> str:
    """白名单分发执行工具调用，任何失败都返回错误文本而非抛异常"""
    try:
        args = json.loads(arguments or "{}")
        if not isinstance(args, dict):
            raise ValueError("参数应为 JSON 对象")
    except ValueError as e:
        return _j({"error": f"工具参数解析失败：{e}"})
    fn = HANDLERS.get(name)
    if fn is None:
        return _j({"error": f"未知工具：{name}"})
    try:
        return fn(db, user, args)
    except Exception as e:  # 工具内部失败回填给模型，由模型向用户解释
        return _j({"error": f"工具执行失败：{e}"})


def summarize(name: str, result: str) -> str:
    """工具结果摘要（前端工具卡片一行预览）"""
    try:
        data = json.loads(result)
        if isinstance(data, dict):
            for key in ("message", "error", "product_name", "name", "keyword"):
                if data.get(key):
                    return str(data[key])[:60]
    except ValueError:
        pass
    return (result or "")[:60]
