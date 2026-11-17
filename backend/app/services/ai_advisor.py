# -*- coding: utf-8 -*-
"""AI 智能导购（REQ 智能导购对话）

解析商品标记/链接/图片/文件并组装价格数据上下文，
调用 OpenAI 兼容大模型生成对话回复。
"""
from datetime import datetime, timedelta

import httpx
import re
from sqlalchemy.orm import Session

from ..config import LLM_API_BASE, LLM_API_KEY, LLM_MODEL
from ..models import Listing, PriceSnapshot, Product


def build_context(db: Session, product_id: int, preference: str = "") -> dict:
    product = db.query(Product).get(product_id)
    if product is None:
        raise ValueError("商品不存在")

    listings = db.query(Listing).filter(Listing.product_id == product_id).all()
    offers = [
        {"platform": l.platform, "price": l.current_price, "url": l.url}
        for l in listings
        if l.current_price
    ]
    offers.sort(key=lambda x: x["price"])

    since_365 = datetime.now() - timedelta(days=365)
    rows = (
        db.query(PriceSnapshot)
        .join(Listing, PriceSnapshot.listing_id == Listing.id)
        .filter(Listing.product_id == product_id, PriceSnapshot.captured_at >= since_365)
        .order_by(PriceSnapshot.captured_at.asc())
        .all()
    )
    daily = {}
    for s in rows:
        d = s.captured_at.strftime("%Y-%m-%d")
        if d not in daily or s.price < daily[d]:
            daily[d] = s.price
    prices = list(daily.values())
    current = offers[0]["price"] if offers else (prices[-1] if prices else None)

    # 历史分位：当前价在一年价格序列中的百分位（越低越好）
    percentile = None
    if current is not None and prices:
        lower = sum(1 for p in prices if p < current)
        percentile = round(lower / len(prices) * 100, 1)

    # 近 7 天 vs 前 7~14 天趋势
    recent = prices[-7:]
    prev = prices[-14:-7]
    trend = "平稳"
    if recent and prev:
        r, p = sum(recent) / len(recent), sum(prev) / len(prev)
        if p > 0:
            change = (r - p) / p * 100
            trend = f"上涨 {change:.1f}%" if change > 2 else (f"下降 {abs(change):.1f}%" if change < -2 else "平稳")

    hist_min = min(prices) if prices else None
    hist_max = max(prices) if prices else None
    return {
        "product_id": product_id,
        "product_name": product.name,
        "category": product.category,
        "current_price": current,
        "history_min": hist_min,
        "history_max": hist_max,
        "history_avg": round(sum(prices) / len(prices), 2) if prices else None,
        "percentile": percentile,
        "trend": trend,
        "history_days": len(prices),
        "offers": offers,
        "preference": preference or "",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def llm_chat(messages: list, temperature: float = 0.5, timeout: int = 60, json_mode: bool = False, ai_config: dict = None) -> str:
    """调用 OpenAI 兼容大模型聊天接口，返回回复文本

    ai_config: 用户自定义模型配置 {api_base, api_key, model}，优先于服务端默认配置
    """
    base = (ai_config or {}).get("api_base") or LLM_API_BASE
    key = (ai_config or {}).get("api_key") or LLM_API_KEY
    model = (ai_config or {}).get("model") or LLM_MODEL
    if not key or not base:
        raise RuntimeError("LLM_API_KEY 未配置")
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    resp = httpx.post(
        f"{base.rstrip('/')}/chat/completions",
        json=payload,
        headers={"Authorization": f"Bearer {key}"},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


# ================= 聊天模式（REQ 智能导购对话） =================

CHAT_SYSTEM_PROMPT = (
    "你是「商品历史价格追踪系统」的 AI 智能导购助手。你可以：\n"
    "1. 基于系统提供的商品数据（当前价、历史价格走势、多平台比价、历史分位）给出购买时机与性价比分析；\n"
    "2. 回答用户关于网购比价、降价提醒、历史价格的疑问；\n"
    "3. 用户发来商品链接时，系统会自动抓取该商品的历史价格数据并随消息附给你。\n"
    "要求：中文回答，简洁友好，用要点分条；涉及价格必须基于提供的数据，不编造；"
    "给出明确操作建议（可立即购买/可关注加购/建议等待降价）。"
)

PRODUCT_TAG_RE = re.compile(r"\[\[product:(\d+)\]\]")
URL_RE = re.compile(r"https?://\S+")


def _product_brief(db: Session, product_id: int) -> tuple:
    """商品 -> 用于 AI 的数据摘要；返回 (摘要文本, 展示名)"""
    try:
        ctx = build_context(db, product_id)
    except ValueError:
        return "", ""
    lines = [
        f"商品：{ctx['product_name']}",
        f"分类：{ctx['category'] or '未分类'}",
        f"当前价：{ctx['current_price']} 元",
        f"历史最低：{ctx['history_min']} 元 / 历史最高：{ctx['history_max']} 元 / 历史均价：{ctx['history_avg']} 元",
        f"当前价历史分位：{ctx['percentile']}%（越低越划算）",
        f"近期趋势：{ctx['trend']}；已收录 {ctx['history_days']} 天价格数据",
    ]
    if len(ctx["offers"]) > 1:
        offers = "、".join(f"{o['platform']} {o['price']}元" for o in ctx["offers"][:5])
        lines.append(f"多平台报价：{offers}")
    return "\n".join(lines), ctx["product_name"]


def _link_brief(url: str) -> str:
    """商品链接 -> 实时抓取历史价格摘要"""
    from .crawler.manmanbuy import query_history

    data = query_history(url, timeout_ms=30000)
    prices = [p for _, p in data["history"]]
    lines = [
        f"商品：{data['title']}",
        f"平台：{data['site_name']}",
        f"当前价：{data['price']} 元",
    ]
    if prices:
        lines.append(
            f"历史最低：{data['history_min']} 元；历史最高：{max(prices)} 元；"
            f"均价：{round(sum(prices) / len(prices), 2)} 元；数据 {len(prices)} 天"
        )
    lines.append(f"来源链接：{url}")
    return "\n".join(lines)


def chat_reply(
    db: Session,
    message: str,
    history: list,
    product_id: int = None,
    images: list = None,
    files: list = None,
    ai_config: dict = None,
) -> dict:
    """AI 导购聊天：解析商品标记/链接/图片/文件 -> 组装上下文 -> 大模型回复

    history: [{role: user|assistant, content}]
    images: [dataURI 或 URL]，以多模态方式传给模型
    files: [{name, url}]，以文本形式告知模型
    ai_config: 用户自定义模型配置 {api_base, api_key, model}，为空走服务端默认模型
    返回 {reply, contexts: [描述], fallback}
    """
    contexts = []
    display = message

    # 0) 图片 / 文件
    if images:
        contexts.append(f"【用户发送了 {len(images)} 张图片，见消息附图】")
    for f in (files or []):
        contexts.append(f"【用户发送了文件：{f.get('name', '')}】（文件内容未提供，仅告知你有此文件）")
        display += f"\n[文件：{f.get('name', '')}]"

    # 1) 解析 [[product:N]] 快捷商品标记
    for pid in PRODUCT_TAG_RE.findall(message):
        brief, name = _product_brief(db, int(pid))
        if brief:
            contexts.append(f"【用户发送的商品 #{pid}】\n{brief}")
            display = PRODUCT_TAG_RE.sub(f"【商品：{name}】", display)

    # 2) 解析链接 -> 实时抓取
    for url in URL_RE.findall(message)[:2]:
        try:
            brief = _link_brief(url)
            contexts.append(f"【用户发送的链接，已抓取详情】\n{brief}")
        except Exception as e:
            contexts.append(f"【用户发送的链接 {url}，抓取失败：{e}】")

    # 3) 路由带入的商品
    if product_id:
        brief, name = _product_brief(db, product_id)
        if brief:
            contexts.append(f"【当前浏览的商品 #{product_id}】\n{brief}")

    # 4) 组装消息
    system = CHAT_SYSTEM_PROMPT
    if contexts:
        system += "\n\n以下是随消息附带的商品数据：\n\n" + "\n\n".join(contexts)

    messages = [{"role": "system", "content": system}]
    for h in (history or [])[-10:]:
        if h.get("role") in ("user", "assistant") and h.get("content"):
            messages.append({"role": h["role"], "content": h["content"]})
    # 当前用户消息（去掉标记，用展示文本）
    current = display
    for url in URL_RE.findall(message):
        if url not in current:
            current += f"\n（链接：{url}）"
    if images:
        content = [{"type": "text", "text": current}]
        content += [{"type": "image_url", "image_url": {"url": u}} for u in images[:4]]
        messages.append({"role": "user", "content": content})
    else:
        messages.append({"role": "user", "content": current})

    try:
        reply = llm_chat(messages, temperature=0.6, timeout=90, ai_config=ai_config)
        return {"reply": reply, "contexts": contexts, "fallback": False}
    except Exception as e:
        # 视觉/网络失败：尝试降级为纯文本重试
        if images:
            try:
                text_only = [m if m.get("role") != "user" or isinstance(m.get("content"), str)
                             else {"role": "user", "content": current}
                             for m in messages]
                reply = llm_chat(text_only, temperature=0.6, timeout=60, ai_config=ai_config)
                return {"reply": reply + "\n\n（注：图片未能被模型解析，已按文字内容回答）",
                        "contexts": contexts, "fallback": False}
            except Exception:
                pass
        if contexts:
            reply = "AI 服务暂时不可用，以下是已获取的数据：\n\n" + "\n\n".join(contexts)
        else:
            label = "自定义模型调用失败" if ai_config else "AI 服务暂时不可用"
            hint = "，可在模型设置中修改配置或切回默认模型" if ai_config else "，请稍后重试"
            reply = f"{label}（{e}）{hint}。"
        return {"reply": reply, "contexts": contexts, "fallback": True}
