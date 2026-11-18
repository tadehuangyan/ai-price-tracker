"""ORM 数据模型定义

覆盖用户、商品/报价/价格快照、追踪与降价提醒，以及后台管理所需的
数据源、采集任务、系统日志/配置、模拟邮箱、敏感词与知识库等数据表。
"""
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    """系统用户：账号、密码哈希、角色与状态"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(191), unique=True, nullable=False, index=True)
    nickname = Column(String(64), default="")
    password_hash = Column(String(128), nullable=False)
    role = Column(String(16), default="user")  # user / admin
    status = Column(String(16), default="active")  # active / disabled
    created_at = Column(DateTime, default=datetime.now)

    # 级联删除：用户删除时一并清理其追踪记录与提醒
    trackings = relationship("Tracking", back_populates="user", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="user", cascade="all, delete-orphan")


class Product(Base):
    """商品：比价与追踪的主体，可关联多个平台报价"""
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, index=True)
    category = Column(String(64), default="", index=True)
    brand = Column(String(64), default="")
    image_url = Column(String(500), default="")
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

    listings = relationship("Listing", back_populates="product", cascade="all, delete-orphan")


class Listing(Base):
    """同一商品在某平台的在售链接（报价）"""
    __tablename__ = "listings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    platform = Column(String(32), nullable=False, index=True)  # jd / taobao / manmanbuy ...
    platform_item_id = Column(String(191), default="")
    url = Column(String(500), default="")
    title = Column(String(255), default="")
    current_price = Column(Float, default=0.0)
    in_stock = Column(Boolean, default=True)
    last_crawled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)

    product = relationship("Product", back_populates="listings")
    snapshots = relationship("PriceSnapshot", back_populates="listing", cascade="all, delete-orphan")

    __table_args__ = (
        # 同一商品在同一平台的站内商品 ID 不重复
        UniqueConstraint("product_id", "platform", "platform_item_id", name="uq_listing"),
    )


class PriceSnapshot(Base):
    """价格快照：某报价在某一时刻的价格采样，用于绘制历史走势"""
    __tablename__ = "price_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    listing_id = Column(Integer, ForeignKey("listings.id"), nullable=False, index=True)
    price = Column(Float, nullable=False)
    captured_at = Column(DateTime, default=datetime.now, index=True)

    listing = relationship("Listing", back_populates="snapshots")

    __table_args__ = (
        # 联合索引：按报价查询时间范围内的快照（历史走势）
        Index("ix_snap_listing_time", "listing_id", "captured_at"),
    )


class Tracking(Base):
    """价格追踪订阅：用户对某商品设定的追踪（含可选目标价）"""
    __tablename__ = "trackings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    target_price = Column(Float, nullable=True)  # 目标价
    created_at = Column(DateTime, default=datetime.now)

    user = relationship("User", back_populates="trackings")
    product = relationship("Product")

    __table_args__ = (
        # 每个用户对同一商品只能有一条追踪记录
        UniqueConstraint("user_id", "product_id", name="uq_user_product"),
    )


class Alert(Base):
    """站内消息 / 降价提醒"""
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    price = Column(Float, nullable=True)
    target_price = Column(Float, nullable=True)
    message = Column(String(500), default="")
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)

    user = relationship("User", back_populates="alerts")
    product = relationship("Product")


class DataSource(Base):
    """数据源配置（REQ-SPT-601）"""
    __tablename__ = "data_sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(32), unique=True, nullable=False)
    name = Column(String(64), default="")
    enabled = Column(Boolean, default=True)
    crawl_interval_minutes = Column(Integer, default=1440)
    config = Column(Text)  # JSON 字符串：选择器、入口地址等
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class CrawlTask(Base):
    """采集任务状态（REQ-SPT-602）"""
    __tablename__ = "crawl_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(32), default="", index=True)
    target = Column(String(500), default="")  # 商品/链接描述
    listing_id = Column(Integer, nullable=True)
    status = Column(String(16), default="pending", index=True)  # pending/running/success/failed/paused
    last_run_at = Column(DateTime, nullable=True)
    last_error = Column(String(500), default="")
    success_count = Column(Integer, default=0)
    fail_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)


class SystemLog(Base):
    """系统日志（REQ-SPT-603）"""
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    level = Column(String(16), default="INFO", index=True)
    module = Column(String(32), default="", index=True)
    message = Column(Text)
    created_at = Column(DateTime, default=datetime.now, index=True)


class SystemConfig(Base):
    """系统配置（REQ-SPT-604）"""
    __tablename__ = "system_config"

    key = Column(String(191), primary_key=True)
    value = Column(Text, default="")
    description = Column(String(255), default="")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class MailMessage(Base):
    """模拟邮箱（沙箱邮件）：不真实外发 SMTP，仅落库模拟投递（REQ 模拟邮箱）"""
    __tablename__ = "mail_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    to_email = Column(String(191), nullable=False, index=True)
    category = Column(String(32), default="system", index=True)  # verify_code/price_alert/subscribe/system
    purpose = Column(String(32), default="")  # 验证码用途：register/email_change/password_change
    subject = Column(String(255), default="")
    body = Column(Text)
    code = Column(String(16), default="")  # 验证码（category=verify_code 时有值）
    code_used = Column(Boolean, default=False)
    is_read = Column(Boolean, default=False)
    status = Column(String(16), default="sent")  # 模拟投递恒为 sent
    created_at = Column(DateTime, default=datetime.now, index=True)

    user = relationship("User")


class SensitiveWord(Base):
    """敏感词库（AI 导购内容过滤）"""
    __tablename__ = "sensitive_words"

    id = Column(Integer, primary_key=True, autoincrement=True)
    word = Column(String(64), unique=True, nullable=False, index=True)
    category = Column(String(32), default="通用")
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)


class KnowledgeArticle(Base):
    """知识库条目（RAG 检索增强）：比价攻略 / 大促规律 / 品类选购指南"""
    __tablename__ = "knowledge_articles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    category = Column(String(64), default="", index=True)
    tags = Column(String(255), default="")  # 逗号分隔关键词（检索命中强信号）
    content = Column(Text, nullable=False)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
