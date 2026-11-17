# -*- coding: utf-8 -*-
"""pytest 公共夹具：SQLite 内存测试库 + TestClient + 数据构造辅助

- 测试库为独立 SQLite 内存库，不触碰 MySQL 业务数据
- 外部网络（爬虫/大模型）在各测试文件中按接口边界 mock
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Alert, Listing, PriceSnapshot, Product, Tracking, User
from app.security import create_token, hash_password
from app.services import moderation

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(engine, "connect")
def _register_sqlite_funcs(dbapi_conn, _record):
    # products.search 的 random 排序使用 MySQL 的 rand()，注册同名函数兼容 SQLite
    dbapi_conn.create_function("rand", 0, random.random)


TestingSession = sessionmaker(bind=engine, autocommit=False)


@pytest.fixture()
def db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    yield session
    session.close()


@pytest.fixture()
def client(db):
    def _override():
        yield db

    app.dependency_overrides[get_db] = _override
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _reset_moderation_cache():
    moderation.invalidate_cache()
    yield
    moderation.invalidate_cache()


# ---------- 数据构造辅助 ----------

def make_user(
    db,
    username="tester",
    email="tester@qq.com",
    password="pass1234",
    role="user",
    status="active",
    nickname="",
):
    u = User(
        username=username,
        email=email,
        nickname=nickname or username,
        password_hash=hash_password(password),
        role=role,
        status=status,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def auth_headers(user):
    return {"Authorization": f"Bearer {create_token(user.id, user.role)}"}


def make_product(db, name="测试手机", category="手机", brand="品牌", image_url=""):
    p = Product(name=name, category=category, brand=brand, image_url=image_url)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def make_listing(
    db,
    product,
    platform="jd",
    url="https://item.jd.com/10001.html",
    title="",
    current_price=100.0,
    last_crawled_at=None,
):
    l = Listing(
        product_id=product.id,
        platform=platform,
        url=url,
        title=title,
        current_price=current_price,
        last_crawled_at=last_crawled_at,
    )
    db.add(l)
    db.commit()
    db.refresh(l)
    return l


def make_snapshot(db, listing, price, captured_at):
    s = PriceSnapshot(listing_id=listing.id, price=price, captured_at=captured_at)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def make_tracking(db, user, product, target_price=None, created_at=None):
    t = Tracking(user_id=user.id, product_id=product.id, target_price=target_price)
    if created_at is not None:
        t.created_at = created_at
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def make_alert(db, user, product=None, price=88.0, target_price=90.0, message="降价提醒", is_read=False):
    a = Alert(
        user_id=user.id,
        product_id=product.id if product else None,
        price=price,
        target_price=target_price,
        message=message,
        is_read=is_read,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def make_code(db, email, purpose):
    """模拟邮箱：生成一枚验证码并返回（测试用）"""
    from app.services.mailer import send_verification_code

    ok, _msg, code = send_verification_code(db, email, purpose)
    assert ok
    return code
