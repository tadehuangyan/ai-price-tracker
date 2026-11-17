# -*- coding: utf-8 -*-
"""定时采集调度（REQ-SPT-302 / 602）

- collect：按数据源配置的频率采集商品价格并写入快照
- alerts：周期性检查目标价并推送降价提醒
"""
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import func

from .database import SessionLocal
from .models import CrawlTask, DataSource, Listing, SystemConfig, SystemLog
from .services.alerts import check_price_alerts

logger = logging.getLogger("spt.scheduler")
scheduler = BackgroundScheduler(timezone="Asia/Shanghai")


def _config(db, key: str, default: str) -> str:
    row = db.query(SystemConfig).get(key)
    return row.value if row and row.value else default


def job_collect():
    """采集所有到点的在售链接价格"""
    from .services.crawler import fetch_price

    db = SessionLocal()
    try:
        interval = int(_config(db, "crawl_interval_minutes", "1440"))
        cutoff = datetime.now() - timedelta(minutes=interval)
        listings = (
            db.query(Listing)
            .filter((Listing.last_crawled_at.is_(None)) | (Listing.last_crawled_at < cutoff))
            .limit(50)
            .all()
        )
        for l in listings:
            task = CrawlTask(platform=l.platform, target=l.url or str(l.id), listing_id=l.id,
                             status="running")
            db.add(task)
            db.commit()
            try:
                data = fetch_price(l.url)
                if data and data.get("price"):
                    l.current_price = data["price"]
                    l.last_crawled_at = datetime.now()
                    l.title = data.get("title") or l.title
                    from .models import PriceSnapshot

                    db.add(PriceSnapshot(listing_id=l.id, price=data["price"]))
                    task.status = "success"
                    task.success_count = 1
                else:
                    task.status = "failed"
                    task.last_error = "未解析到价格"
                    task.fail_count = 1
            except Exception as e:
                task.status = "failed"
                task.last_error = str(e)[:480]
                task.fail_count = 1
                db.add(SystemLog(level="ERROR", module="crawl",
                                 message=f"采集失败 {l.url}: {e}"))
            task.last_run_at = datetime.now()
            db.commit()
    except Exception as e:
        logger.exception("collect job error: %s", e)
    finally:
        db.close()


def job_alerts():
    db = SessionLocal()
    try:
        n = check_price_alerts(db)
        if n:
            db.add(SystemLog(level="INFO", module="alert", message=f"产生 {n} 条降价提醒"))
            db.commit()
    except Exception as e:
        logger.exception("alerts job error: %s", e)
    finally:
        db.close()


def start_scheduler():
    # 启动后延迟执行一轮采集（后台进行，不阻塞服务启动）
    scheduler.add_job(
        job_collect, "date",
        run_date=datetime.now() + timedelta(seconds=5),
        id="collect_once", replace_existing=True,
    )
    scheduler.add_job(job_collect, "interval", minutes=30, id="collect",
                      replace_existing=True, max_instances=1)
    scheduler.add_job(job_alerts, "interval", minutes=10, id="alerts",
                      replace_existing=True, max_instances=1)
    if not scheduler.running:
        scheduler.start()
    logger.info("scheduler started")
