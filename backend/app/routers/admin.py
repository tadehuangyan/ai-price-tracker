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
    Listing,
    PriceSnapshot,
    Product,
    SensitiveWord,
    SystemConfig,
    SystemLog,
    Tracking,
    User,
)
from ..schemas import ConfigIn, DataSourceIn, SensitiveWordBatchIn, SensitiveWordIn, UserOut
from ..services.crawler import run_crawl_task
from ..services.moderation import invalidate_cache

router = APIRouter(prefix="/api/admin", tags=["系统管理"])


def log(db: Session, module: str, message: str, level: str = "INFO"):
    db.add(SystemLog(level=level, module=module, message=message))
    db.commit()


# ---------- REQ-SPT-601 数据源管理 ----------

@router.get("/datasources")
def list_datasources(db: Session = Depends(get_db), _=Depends(require_admin)):
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
    q = db.query(CrawlTask)
    if status:
        q = q.filter(CrawlTask.status == status)
    total = q.count()
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
    t = db.query(CrawlTask).get(task_id)
    if t is None:
        raise HTTPException(404, "任务不存在")
    t.status = "paused"
    db.commit()
    return {"ok": True}


@router.post("/tasks/{task_id}/resume")
def resume_task(task_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    t = db.query(CrawlTask).get(task_id)
    if t is None:
        raise HTTPException(404, "任务不存在")
    t.status = "pending"
    db.commit()
    return {"ok": True}


# ---------- REQ-SPT-603 统计数据与系统日志 ----------

@router.get("/stats")
def stats(db: Session = Depends(get_db), _=Depends(require_admin)):
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
    invalidate_cache()
    log(db, "moderation", f"批量导入敏感词：新增 {added} 个，跳过 {skipped} 个")
    return {"ok": True, "added": added, "skipped": skipped}


@router.delete("/sensitive-words/{word_id}")
def delete_sensitive_word(word_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    row = db.query(SensitiveWord).get(word_id)
    if row is None:
        raise HTTPException(404, "敏感词不存在")
    word = row.word
    db.delete(row)
    db.commit()
    invalidate_cache()
    log(db, "moderation", f"删除敏感词：{word}")
    return {"ok": True}
