"""系统管理路由：数据源、采集任务、统计/日志、系统配置、用户与敏感词/知识库管理

全部接口均要求管理员权限（require_admin）。
"""
import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_admin
from ..models import (
    Alert,
    CrawlTask,
    DataSource,
    KnowledgeArticle,
    Listing,
    PriceSnapshot,
    Product,
    SensitiveWord,
    SystemConfig,
    SystemLog,
    Tracking,
    User,
)
from ..schemas import ConfigIn, DataSourceIn, KnowledgeIn, SensitiveWordBatchIn, SensitiveWordIn, UserOut
from ..services.crawler import run_crawl_task
from ..services.moderation import invalidate_cache

router = APIRouter(prefix="/api/admin", tags=["系统管理"])


def log(db: Session, module: str, message: str, level: str = "INFO"):
    """写系统日志并立即提交（管理操作留痕）"""
    db.add(SystemLog(level=level, module=module, message=message))
    db.commit()


# ---------- REQ-SPT-601 数据源管理 ----------

@router.get("/datasources")
def list_datasources(db: Session = Depends(get_db), _=Depends(require_admin)):
    """查询全部数据源配置"""
    rows = db.query(DataSource).order_by(DataSource.id).all()
    return [
        {
            "id": d.id,
            "platform": d.platform,
            "name": d.name,
            "enabled": d.enabled,
            "crawl_interval_minutes": d.crawl_interval_minutes,
            "config": d.config,
            "updated_at": d.updated_at.strftime("%Y-%m-%d %H:%M") if d.updated_at else None,
        }
        for d in rows
    ]


@router.post("/datasources")
def save_datasource(body: DataSourceIn, db: Session = Depends(get_db), _=Depends(require_admin)):
    """新增或更新数据源配置（按 platform 幂等，已存在则覆盖字段）"""
    d = db.query(DataSource).filter(DataSource.platform == body.platform).first()
    if d is None:
        d = DataSource(platform=body.platform)
        db.add(d)
    d.name = body.name or d.name or body.platform
    d.enabled = body.enabled
    d.crawl_interval_minutes = body.crawl_interval_minutes
    d.config = body.config or "{}"
    db.commit()
    log(db, "datasource", f"更新数据源 {body.platform}: enabled={body.enabled}")
    return {"ok": True}


# ---------- REQ-SPT-602 采集任务调度与监控 ----------

@router.get("/tasks")
def list_tasks(
    status: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    """采集任务列表：按状态筛选，分页返回（倒序）"""
    q = db.query(CrawlTask)
    if status:
        q = q.filter(CrawlTask.status == status)
    total = q.count()
    # 分页：offset = (页码 - 1) * 每页条数
    rows = q.order_by(CrawlTask.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": t.id,
                "platform": t.platform,
                "target": t.target,
                "status": t.status,
                "last_run_at": t.last_run_at.strftime("%Y-%m-%d %H:%M:%S") if t.last_run_at else None,
                "last_error": t.last_error,
                "success_count": t.success_count,
                "fail_count": t.fail_count,
            }
            for t in rows
        ],
    }


@router.post("/tasks/{task_id}/run")
def run_task_now(task_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    """立即手动执行一次指定采集任务，返回执行结果"""
    t = db.query(CrawlTask).get(task_id)
    if t is None:
        raise HTTPException(404, "任务不存在")
    t.status = "running"
    db.commit()
    ok, err = run_crawl_task(db, t)
    log(db, "task", f"手动执行任务 #{task_id}({t.platform}) -> {'成功' if ok else '失败: ' + err}",
        level="INFO" if ok else "ERROR")
    return {"ok": ok, "error": err}


@router.post("/tasks/{task_id}/pause")
def pause_task(task_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    """暂停采集任务（状态置为 paused）"""
    t = db.query(CrawlTask).get(task_id)
    if t is None:
        raise HTTPException(404, "任务不存在")
    t.status = "paused"
    db.commit()
    return {"ok": True}


@router.post("/tasks/{task_id}/resume")
def resume_task(task_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    """恢复采集任务（状态重置为 pending，等待下轮调度）"""
    t = db.query(CrawlTask).get(task_id)
    if t is None:
        raise HTTPException(404, "任务不存在")
    t.status = "pending"
    db.commit()
    return {"ok": True}


# ---------- REQ-SPT-603 统计数据与系统日志 ----------

@router.get("/stats")
def stats(db: Session = Depends(get_db), _=Depends(require_admin)):
    """系统统计概览：商品/报价/快照/用户/追踪/提醒数量与采集成功率"""
    total_tasks = db.query(CrawlTask).count()
    success = db.query(CrawlTask).filter(CrawlTask.status == "success").count()
    failed = db.query(CrawlTask).filter(CrawlTask.status == "failed").count()
    done = success + failed
    day_ago = datetime.now() - timedelta(days=1)
    recent_total = db.query(CrawlTask).filter(CrawlTask.last_run_at >= day_ago).count()
    recent_success = (
        db.query(CrawlTask)
        .filter(CrawlTask.last_run_at >= day_ago, CrawlTask.status == "success")
        .count()
    )
    return {
        "product_count": db.query(Product).count(),
        "listing_count": db.query(Listing).count(),
        "snapshot_count": db.query(PriceSnapshot).count(),
        "user_count": db.query(User).count(),
        "tracking_count": db.query(Tracking).count(),
        "alert_count": db.query(Alert).count(),
        "task_total": total_tasks,
        "task_success": success,
        "task_failed": failed,
        # 成功率按最近 24 小时的任务统计，无任务时不返回
        "success_rate": round(recent_success / recent_total * 100, 1) if recent_total else None,
    }


@router.get("/logs")
def logs(
    level: str = Query(""),
    module: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    """系统日志查询：按级别/模块筛选，分页返回（倒序）"""
    q = db.query(SystemLog)
    if level:
        q = q.filter(SystemLog.level == level)
    if module:
        q = q.filter(SystemLog.module == module)
    total = q.count()
    rows = q.order_by(SystemLog.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": r.id,
                "level": r.level,
                "module": r.module,
                "message": r.message,
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else None,
            }
            for r in rows
        ],
    }


# ---------- REQ-SPT-604 系统配置 ----------

@router.get("/config")
def get_config(db: Session = Depends(get_db), _=Depends(require_admin)):
    """查询全部系统配置项"""
    rows = db.query(SystemConfig).all()
    return [
        {
            "key": c.key,
            "value": c.value,
            "description": c.description,
            "updated_at": c.updated_at.strftime("%Y-%m-%d %H:%M") if c.updated_at else None,
        }
        for c in rows
    ]


@router.put("/config")
def set_config(body: ConfigIn, db: Session = Depends(get_db), _=Depends(require_admin)):
    """更新系统配置（键不存在则创建）"""
    c = db.query(SystemConfig).get(body.key)
    if c is None:
        c = SystemConfig(key=body.key)
        db.add(c)
    c.value = body.value
    db.commit()
    log(db, "config", f"更新系统配置 {body.key}")
    return {"ok": True}


# ---------- 用户管理（REQ-SPT-104）----------

@router.get("/users")
def list_users(
    keyword: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    """用户列表：按用户名/邮箱模糊搜索，分页返回"""
    q = db.query(User)
    if keyword:
        q = q.filter((User.username.contains(keyword)) | (User.email.contains(keyword)))
    total = q.count()
    rows = q.order_by(User.id).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [UserOut.model_validate(u).model_dump(mode="json") for u in rows],
    }


@router.post("/users/{user_id}/status")
def set_user_status(
    user_id: int,
    status: str = Query(..., pattern="^(active|disabled)$"),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """启用/禁用用户账号（禁止管理员禁用自己）"""
    u = db.query(User).get(user_id)
    if u is None:
        raise HTTPException(404, "用户不存在")
    if u.id == admin.id:
        raise HTTPException(400, "不能禁用自己")
    u.status = status
    db.commit()
    log(db, "user", f"管理员 {admin.username} 将用户 {u.username} 设为 {status}")
    return {"ok": True}


# ---------- 敏感词管理（AI 导购内容过滤） ----------

@router.get("/sensitive-words")
def list_sensitive_words(
    keyword: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    """敏感词列表：按关键词模糊搜索，分页返回"""
    q = db.query(SensitiveWord)
    if keyword:
        q = q.filter(SensitiveWord.word.contains(keyword))
    total = q.count()
    rows = q.order_by(SensitiveWord.id).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": r.id,
                "word": r.word,
                "category": r.category,
                "enabled": r.enabled,
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else None,
            }
            for r in rows
        ],
    }


@router.post("/sensitive-words")
def add_sensitive_word(body: SensitiveWordIn, db: Session = Depends(get_db), _=Depends(require_admin)):
    """新增单个敏感词（去空格、查重），并刷新内容过滤缓存"""
    word = body.word.strip()
    if not word:
        raise HTTPException(400, "敏感词不能为空")
    if db.query(SensitiveWord).filter(SensitiveWord.word == word).first():
        raise HTTPException(400, "该敏感词已存在")
    db.add(SensitiveWord(word=word, category=body.category or "通用"))
    db.commit()
    invalidate_cache()
    log(db, "moderation", f"新增敏感词：{word}")
    return {"ok": True}


@router.post("/sensitive-words/batch")
def add_sensitive_words_batch(
    body: SensitiveWordBatchIn, db: Session = Depends(get_db), _=Depends(require_admin)
):
    """批量导入敏感词：按行拆分，跳过空行/超长/重复词，返回新增与跳过数量"""
    lines = [w.strip() for w in body.words.splitlines()]
    added, skipped = 0, 0
    for word in lines:
        if not word or len(word) > 64:
            skipped += 1
            continue
        if db.query(SensitiveWord).filter(SensitiveWord.word == word).first():
            skipped += 1
            continue
        db.add(SensitiveWord(word=word, category=body.category or "通用"))
        added += 1
    db.commit()
    # 词库变更后使内存缓存失效，下次过滤时重新加载
    invalidate_cache()
    log(db, "moderation", f"批量导入敏感词：新增 {added} 个，跳过 {skipped} 个")
    return {"ok": True, "added": added, "skipped": skipped}


@router.delete("/sensitive-words/{word_id}")
def delete_sensitive_word(word_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    """删除指定敏感词，并刷新内容过滤缓存"""
    row = db.query(SensitiveWord).get(word_id)
    if row is None:
        raise HTTPException(404, "敏感词不存在")
    word = row.word
    db.delete(row)
    db.commit()
    invalidate_cache()
    log(db, "moderation", f"删除敏感词：{word}")
    return {"ok": True}


# ---------- 知识库管理（RAG 检索增强） ----------

@router.get("/knowledge")
def list_knowledge(
    keyword: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    """知识库条目列表：按标题/标签/正文模糊搜索，分页返回"""
    q = db.query(KnowledgeArticle)
    if keyword:
        q = q.filter(
            KnowledgeArticle.title.contains(keyword)
            | KnowledgeArticle.tags.contains(keyword)
            | KnowledgeArticle.content.contains(keyword)
        )
    total = q.count()
    rows = q.order_by(KnowledgeArticle.id).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": r.id,
                "title": r.title,
                "category": r.category,
                "tags": r.tags,
                "content": r.content,
                "enabled": r.enabled,
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else None,
            }
            for r in rows
        ],
    }


@router.post("/knowledge")
def create_knowledge(body: KnowledgeIn, db: Session = Depends(get_db), _=Depends(require_admin)):
    """新增知识库条目（供 AI 导购 RAG 检索）"""
    db.add(KnowledgeArticle(
        title=body.title.strip(),
        category=(body.category or "").strip(),
        tags=(body.tags or "").strip(),
        content=body.content.strip(),
        enabled=body.enabled,
    ))
    db.commit()
    log(db, "knowledge", f"新增知识条目：{body.title}")
    return {"ok": True}


@router.put("/knowledge/{article_id}")
def update_knowledge(
    article_id: int, body: KnowledgeIn, db: Session = Depends(get_db), _=Depends(require_admin)
):
    """更新指定知识库条目内容"""
    row = db.query(KnowledgeArticle).get(article_id)
    if row is None:
        raise HTTPException(404, "知识条目不存在")
    row.title = body.title.strip()
    row.category = (body.category or "").strip()
    row.tags = (body.tags or "").strip()
    row.content = body.content.strip()
    row.enabled = body.enabled
    db.commit()
    log(db, "knowledge", f"更新知识条目：{row.title}")
    return {"ok": True}


@router.delete("/knowledge/{article_id}")
def delete_knowledge(article_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    """删除指定知识库条目"""
    row = db.query(KnowledgeArticle).get(article_id)
    if row is None:
        raise HTTPException(404, "知识条目不存在")
    title = row.title
    db.delete(row)
    db.commit()
    log(db, "knowledge", f"删除知识条目：{title}")
    return {"ok": True}
