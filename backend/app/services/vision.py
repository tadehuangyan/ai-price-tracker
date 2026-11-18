# -*- coding: utf-8 -*-
"""识图服务（多模态闭环）：图片 -> 视觉模型提取商品关键词 -> 供搜索/比价使用

视觉模型由 LLM_VISION_MODEL 指定（OpenAI 兼容多模态接口），未配置时回退默认模型；
调用/解析失败抛异常，由路由层降级提示。
"""
import json
import re

from ..config import LLM_VISION_MODEL
from .ai_advisor import llm_chat

VISION_SYSTEM = (
    "你是商品识别助手。识别图片中的商品，只输出一个 JSON 对象，不要输出其它文字：\n"
    '{"keywords":"用于电商搜索的关键词（品牌+型号+品类，10 字以内）","category":"品类","confidence":0到1}\n'
    "认不出商品时 keywords 输出空字符串。"
)


def _parse(raw: str) -> dict:
    """解析视觉模型输出：正则提取 JSON 块并做字段裁剪/置信度夹取（解析失败抛 ValueError）"""
    m = re.search(r"\{.*\}", raw or "", re.S)  # 模型可能夹带解释文字，只取其中的 JSON 对象
    if not m:
        raise ValueError("视觉模型未返回可解析结果")
    data = json.loads(m.group(0))
    return {
        # 关键词/品类截断防超长，confidence 强制夹取到 [0, 1]
        "keywords": str(data.get("keywords", "")).strip()[:40],
        "category": str(data.get("category", "")).strip()[:20],
        "confidence": max(0.0, min(1.0, float(data.get("confidence", 0.5)))),
    }


def image_keywords(images: list, ai_config: dict = None) -> dict:
    """图片 -> {keywords, category, confidence}（keywords 为空表示未识别出商品）"""
    if not images:
        raise ValueError("缺少图片")
    # 多模态消息：文本指令 + image_url 列表（dataURI/URL），最多取 2 张
    content = [{"type": "text", "text": "识别这张图片中的商品，输出 JSON。"}]
    content += [{"type": "image_url", "image_url": {"url": u}} for u in images[:2]]
    msgs = [{"role": "system", "content": VISION_SYSTEM}, {"role": "user", "content": content}]
    cfg = dict(ai_config or {})
    if LLM_VISION_MODEL:
        cfg["model"] = LLM_VISION_MODEL  # 专用视觉模型优先于用户配置的文本模型
    raw = llm_chat(msgs, temperature=0.1, timeout=60, ai_config=cfg or None)  # 低温保证输出稳定
    return _parse(raw)
