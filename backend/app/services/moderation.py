# -*- coding: utf-8 -*-
"""敏感词过滤（AI 导购输入/输出内容安全）

词库存于 sensitive_words 表，内存缓存 60 秒；
管理端增删词后调用 invalidate_cache() 立即生效。
匹配规则：大小写不敏感的子串匹配。
"""
import time

from sqlalchemy.orm import Session

from ..models import SensitiveWord

CACHE_TTL = 60  # 秒
_cache = {"words": None, "expires": 0.0}


def get_words(db: Session) -> list:
    """返回启用中的敏感词列表（带缓存）"""
    now = time.time()
    if _cache["words"] is not None and now < _cache["expires"]:
        return _cache["words"]
    words = [
        w.word
        for w in db.query(SensitiveWord).filter(SensitiveWord.enabled.is_(True)).all()
    ]
    _cache["words"] = words
    _cache["expires"] = now + CACHE_TTL
    return words


def invalidate_cache():
    """词库变更后调用，下次请求重新加载"""
    _cache["words"] = None
    _cache["expires"] = 0.0


def find_sensitive(text: str, db: Session) -> list:
    """返回 text 中命中的敏感词列表（去重，按词库顺序）"""
    if not text:
        return []
    lowered = text.lower()
    hits = []
    for word in get_words(db):
        w = word.strip()
        if w and w.lower() in lowered and w not in hits:
            hits.append(w)
    return hits
