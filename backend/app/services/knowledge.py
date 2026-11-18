# -*- coding: utf-8 -*-
"""轻量 RAG 检索（知识库）：关键词召回 + 加权重排，零外部依赖

检索策略（对 SQLite/MySQL 均可移植，不依赖全文索引）：
- tags 命中（强信号）：知识条目预置关键词出现在查询中；
- 标题/正文命中：查询切 2-gram 参与匹配，命中数加权；
- 得分超过阈值按 top-N 返回，附来源信息（id/title）供回答标注引用。
"""
import re

from sqlalchemy.orm import Session

from ..models import KnowledgeArticle

# 无检索意义的常见字（参与 2-gram 时过滤，降噪）
STOP_CHARS = set("的了吗呢吧啊是我你他她它们这那个有和与在是个就都也很再还想要请问一下什么怎么如何")
MIN_SCORE = 2  # 低于该得分视为不相关
CONTENT_LIMIT = 600  # 注入 Prompt 的正文截断长度


def _tokens(query: str) -> set:
    """查询切词：中文 2-gram + 英文/数字单词（长度 >= 2）"""
    q = re.sub(r"[^\w\u4e00-\u9fff]+", " ", query or "")
    tokens = set()
    for word in q.split():
        if re.match(r"^[a-zA-Z0-9]+$", word):
            if len(word) >= 2:
                tokens.add(word.lower())
            continue
        chars = [c for c in word if c not in STOP_CHARS]
        for i in range(len(chars) - 1):
            tokens.add("".join(chars[i:i + 2]))
    return tokens


def retrieve(db: Session, query: str, limit: int = 3):
    """检索知识库：返回 (知识上下文列表, 来源列表 [{"id", "title"}])

    上下文形如 "【知识库 K3｜标题】\\n正文…"，来源列表供回答标注引用与前端展示。
    """
    if not (query or "").strip():
        return [], []
    tokens = _tokens(query)
    scored = []
    # 逐条打分（零外部依赖的轻量混合检索：关键词召回 + 加权重排）
    for a in db.query(KnowledgeArticle).filter(KnowledgeArticle.enabled.is_(True)).all():
        score = 0
        # tags 命中为强信号：条目预置关键词直接出现在查询中加 5 分
        for tag in [t.strip() for t in (a.tags or "").split(",") if t.strip()]:
            if tag and tag.lower() in query.lower():
                score += 5
        title = (a.title or "").lower()
        content = (a.content or "").lower()
        # 2-gram/单词命中加权：标题命中（+2）比正文命中（+1）更能代表主题相关
        for tok in tokens:
            if tok in title:
                score += 2
            elif tok in content:
                score += 1
        if score >= MIN_SCORE:
            scored.append((score, a))
    # 得分降序，同分按 id 稳定排序，取 top-N
    scored.sort(key=lambda x: (-x[0], x[1].id))
    picked = [a for _, a in scored[:limit]]
    # 上下文正文截断注入 Prompt；来源列表供回答标注【来源：Kx】与前端展示
    contexts = [
        f"【知识库 K{a.id}｜{a.title}】\n{(a.content or '')[:CONTENT_LIMIT]}"
        for a in picked
    ]
    sources = [{"id": a.id, "title": a.title} for a in picked]
    return contexts, sources
