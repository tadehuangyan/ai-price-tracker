"""数据库连接与会话管理：创建 SQLAlchemy 引擎、会话工厂与 ORM 声明基类"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from .config import DATABASE_URL

# pool_pre_ping 取连接前先探活、pool_recycle 定期回收，避免 MySQL 长连接被服务端断开
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=3600)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)  # 会话工厂
Base = declarative_base()  # 所有 ORM 模型的基类


def get_db():
    """FastAPI 依赖：为每个请求提供独立数据库会话，请求结束后关闭"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
