# -*- coding: utf-8 -*-
"""内容安全（AI 导购输入/输出）

- 敏感词过滤：词库存于 sensitive_words 表，内存缓存 60 秒；
  管理端增删词后调用 invalidate_cache() 立即生效。匹配规则：大小写不敏感的子串匹配。
- 提示注入检测（AI 安全）：识别用户消息中试图操控模型的指令模式
  （越狱/忽略规则/套取提示词等），与敏感词同款拦截。
"""
import re
import time

from sqlalchemy.orm import Session

from ..models import SensitiveWord

CACHE_TTL = 60  # 秒
_cache = {"words": None, "expires": 0.0}


def get_words(db: Session) -> list:
    """返回启用中的敏感词列表（带缓存）"""
    now = time.time()
    if _cache["words"] is not None and now < _cache["expires"]:
        return _cache["words"]  # 缓存未过期直接复用，避免每次输出都查库
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
    lowered = text.lower()  # 统一小写后做子串匹配，规避大小写变形
    hits = []
    for word in get_words(db):
        w = word.strip()
        if w and w.lower() in lowered and w not in hits:
            hits.append(w)
    return hits


def max_word_len(db: Session) -> int:
    """最长敏感词长度（流式输出的回看窗口：尾部保留该长度再放行）"""
    return max((len(w.strip()) for w in get_words(db)), default=0)


# ================= 提示注入检测（AI 安全） =================

# 每条为 (正则, 标签)：覆盖忽略指令/篡改角色/套取提示词/越狱等常见注入手法
INJECTION_PATTERNS = [
    (r"忽略(?:(?:以上|上面|之前|前面|上述|所有|全部|这些)(?:的)?){1,2}(?:指令|提示|内容|对话|设定|规则|限制)", "忽略既有指令"),
    (r"忘记(?:(?:以上|之前|此前|你的|所有)(?:的)?){1,2}(?:指令|设定|角色|规则|限制)", "篡改角色设定"),
    (r"ignore\s+(?:all\s+)?(?:previous|above|prior|earlier)\s+(?:instructions|prompts|messages|rules)", "英文提示注入"),
    (r"disregard\s+(?:all\s+)?(?:previous|above|prior|earlier)\s+(?:instructions|prompts)", "英文提示注入"),
    (r"(?:显示|打印|输出|透露|泄露|重复|复述)(?:你的)?(?:系统)?(?:提示词|指令|设定)", "套取系统提示词"),
    (r"(?:system\s*prompt|system\s*message)\s*(?:是|:|＝|=|是什么)", "套取系统提示词"),
    (r"你现在(?:是|扮演|充当)(?:一个)?(?:没有|不受|无需)(?:任何)?(?:限制|约束|规则)", "越狱指令"),
    (r"(?:越狱|jailbreak|DAN\s*模式|开发者模式)", "越狱指令"),
    (r"(?:所有|全部|其他|其余)用户的?.{0,12}(?:资料|数据|信息|密码|隐私|账号|记录).{0,10}(?:发|传|交).{0,4}(?:我|出来|一下)", "窃取用户数据"),
    (r"泄露.{0,8}(?:用户|客户|所有人).{0,8}(?:数据|资料|信息|隐私|密码)", "窃取用户数据"),
]
INJECTION_RES = [(re.compile(p, re.I), label) for p, label in INJECTION_PATTERNS]  # 预编译，供逐条匹配复用


def find_injection(text: str) -> list:
    """返回 text 中命中的提示注入模式标签（去重，按规则顺序）"""
    if not text:
        return []
    hits = []
    for rx, label in INJECTION_RES:
        if rx.search(text) and label not in hits:
            hits.append(label)
    return hits
