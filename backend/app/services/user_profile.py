# -*- coding: utf-8 -*-
"""用户画像（个性化消费建议）：以 Markdown 文件持久化，Agent 可读写

文件：backend/storage/profiles/user_{id}.md
结构：标题 + 说明 + 按类别分节（消费偏好/预算区间/关注商品/购买习惯），
条目以 "- YYYY-MM-DD 内容" 追加并去重；读取时压缩为文本注入对话上下文。
"""
import os
import re
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROFILE_DIR = os.path.join(BASE_DIR, "storage", "profiles")

# 工具入参类别 -> MD 小节名
SECTIONS = {
    "偏好": "消费偏好",
    "预算": "预算区间",
    "关注": "关注商品",
    "习惯": "购买习惯",
}
SECTION_ORDER = ["消费偏好", "预算区间", "关注商品", "购买习惯"]
MAX_NOTE_LEN = 120  # 单条记录长度上限
MAX_ITEMS = 20  # 每节条目上限（超出丢弃最旧）

HEADER = (
    "# 用户画像（AI 智能导购自动整理）\n\n"
    "> 来源：对话中了解到的消费偏好 / 预算 / 关注 / 习惯，用于提供个性化消费建议。\n"
)


def profile_path(user_id: int) -> str:
    """画像文件路径：storage/profiles/user_{id}.md"""
    return os.path.join(PROFILE_DIR, f"user_{user_id}.md")


def read_profile(user_id: int) -> str:
    """读取画像 MD 全文（不存在返回空串）"""
    path = profile_path(user_id)
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read()


def _parse_sections(text: str) -> dict:
    """解析画像 MD -> {小节名: [条目]}：识别 ## 小节标题，条目去掉日期前缀"""
    sections = {name: [] for name in SECTION_ORDER}
    current = None
    for line in (text or "").splitlines():
        m = re.match(r"^##\s+(.+)$", line.strip())
        if m:
            current = m.group(1).strip()
            continue
        # 条目形如 "- 2026-01-01 内容"，去掉列表符与日期前缀只留事实文本
        item = re.sub(r"^-\s+(?:\d{4}-\d{2}-\d{2}\s+)?", "", line.strip())
        if current in sections and line.strip().startswith("-") and item:
            sections[current].append(item)
    return sections


def write_profile(user_id: int, content: str) -> None:
    """整文覆盖写入画像 MD（个人中心手动编辑用）"""
    os.makedirs(PROFILE_DIR, exist_ok=True)
    text = content or ""
    if text.strip() and not text.endswith("\n"):
        text += "\n"
    with open(profile_path(user_id), "w", encoding="utf-8") as f:
        f.write(text)


def record_note(user_id: int, category: str, note: str) -> dict:
    """记录一条画像事实（文本级插入对应小节，保留用户手编的其它内容）

    category 支持简称（偏好/预算/关注/习惯）或小节全名，未知归入"消费偏好"；
    与已有条目重复时不重复记录。返回 {ok, section, note, duplicated}。
    """
    note = re.sub(r"\s+", " ", (note or "").strip())[:MAX_NOTE_LEN]  # 压缩空白并截断超长内容
    if not note:
        return {"ok": False, "error": "记录内容为空"}
    # 类别映射：支持简称，未知类别归入「消费偏好」
    section = SECTIONS.get((category or "").strip()) or (
        category.strip() if category and category.strip() in SECTION_ORDER else "消费偏好"
    )
    text = read_profile(user_id)
    # 去重：同内容条目（忽略日期前缀）已存在则不重复记录
    if re.search(r"(?m)^-\s+(?:\d{4}-\d{2}-\d{2}\s+)?" + re.escape(note) + r"\s*$", text):
        return {"ok": True, "section": section, "note": note, "duplicated": True}
    if not text.strip():
        text = HEADER
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.strip() == f"## {section}"), None)
    if start is None:
        # 新小节追加到文末
        if lines and lines[-1].strip():
            lines.append("")
        lines += [f"## {section}", "", f"- {note}", ""]
    else:
        # 定位小节范围（下一个 ## 之前），新条目插到小节末尾的非空行后
        end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
        item_idx = [i for i in range(start + 1, end) if lines[i].strip().startswith("- ")]
        drop = item_idx[0] if len(item_idx) >= MAX_ITEMS else None  # 超限丢最旧一条
        insert_at = end
        while insert_at > start + 1 and not lines[insert_at - 1].strip():
            insert_at -= 1
        lines.insert(insert_at, f"- {note}")
        if drop is not None:
            lines[drop] = None  # type: ignore[assignment]
        lines = [ln for ln in lines if ln is not None]  # type: ignore[comparison-overlap]
    os.makedirs(PROFILE_DIR, exist_ok=True)
    with open(profile_path(user_id), "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")
    return {"ok": True, "section": section, "note": note, "duplicated": False}


def build_context(user_id: int) -> str:
    """画像 -> 注入对话的紧凑文本（无内容返回空串）"""
    sections = _parse_sections(read_profile(user_id))
    lines = []
    for name in SECTION_ORDER:
        items = sections.get(name) or []
        if items:
            # 每节最多取 8 条，避免画像过长挤占对话上下文
            lines.append(f"- {name}：" + "；".join(items[:8]))
    if not lines:
        return ""
    return "【用户画像】（历史对话自动整理）\n" + "\n".join(lines)[:800]  # 整体限 800 字
