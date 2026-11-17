import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .database import Base, SessionLocal, engine
from .models import DataSource, SensitiveWord, SystemConfig, SystemLog, User
from .routers import admin, ai, auth, compare, mail, products, tracking
from .scheduler import start_scheduler
from .security import hash_password

logging.basicConfig(level=logging.INFO)


def seed(db):
    """初始化：建表、默认管理员、数据源、系统配置"""
    if db.query(User).filter(User.username == "admin").first() is None:
        db.add(
            User(
                username="admin",
                email="admin@spt.local",
                nickname="系统管理员",
                password_hash=hash_password("admin123456"),
                role="admin",
            )
        )
    defaults = [
        ("jd", "京东", True, "{}"),
        ("taobao", "淘宝/天猫", False, "{}"),
        ("manmanbuy", "慢慢买（历史价格）", True, "{}"),
        ("dangdang", "当当", False, "{}"),
        ("suning", "苏宁易购", False, "{}"),
    ]
    for platform, name, enabled, cfg in defaults:
        if db.query(DataSource).filter(DataSource.platform == platform).first() is None:
            db.add(
                DataSource(
                    platform=platform, name=name, enabled=enabled,
                    crawl_interval_minutes=1440, config=cfg,
                )
            )
    for key, value, desc in [
        ("crawl_interval_minutes", "1440", "采集频率（分钟）"),
        ("alert_check_minutes", "10", "降价提醒检查间隔（分钟）"),
        ("ai_service_base", "", "AI 服务接口地址（留空则读 .env）"),
        ("max_track_per_user", "30", "每用户追踪商品上限"),
    ]:
        if db.query(SystemConfig).get(key) is None:
            db.add(SystemConfig(key=key, value=value, description=desc))
    for word, category in [
        ("赌博", "违法"),
        ("代开发票", "违法"),
        ("诈骗", "违法"),
        ("传销", "违法"),
        ("枪支", "违禁品"),
        ("毒品", "违禁品"),
    ]:
        if db.query(SensitiveWord).filter(SensitiveWord.word == word).first() is None:
            db.add(SensitiveWord(word=word, category=category))
    if db.query(SystemLog).count() == 0:
        db.add(SystemLog(module="system", message="系统初始化完成"))
    db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()
    start_scheduler()
    yield


app = FastAPI(title="商品历史价格追踪系统 (SPT)", version="1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(mail.router)
app.include_router(products.router)
app.include_router(tracking.router)
app.include_router(compare.router)
app.include_router(ai.router)
app.include_router(admin.router)

# 上传文件静态访问（聊天发送的文件）
import os as _os

_updir = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "storage", "uploads")
_os.makedirs(_updir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=_updir), name="uploads")


@app.get("/api/health")
def health():
    return {"ok": True, "service": "SPT"}
