from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


# ---------- 用户管理 ----------

class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=20)
    password: str = Field(min_length=8, max_length=64)
    email: EmailStr
    nickname: Optional[str] = None
    code: Optional[str] = None  # 模拟邮箱验证码


class LoginIn(BaseModel):
    username: str
    password: str
    remember: bool = False


class ProfileUpdate(BaseModel):
    nickname: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    email_code: Optional[str] = None  # 换绑邮箱验证码
    password_code: Optional[str] = None  # 修改密码验证码


class SendCodeIn(BaseModel):
    email: EmailStr
    purpose: str = Field(pattern="^(register|email_change|password_change)$")


class VerifyCodeIn(SendCodeIn):
    code: str = Field(min_length=6, max_length=6)


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    nickname: str
    role: str
    status: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---------- 商品查询 ----------

class ListingOut(BaseModel):
    id: int
    platform: str
    url: str
    title: str
    current_price: float
    last_crawled_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ProductOut(BaseModel):
    id: int
    name: str
    category: str
    brand: str
    image_url: str
    description: Optional[str] = None
    min_price: Optional[float] = None
    listings: List[ListingOut] = []

    class Config:
        from_attributes = True


class Page(BaseModel):
    total: int
    page: int
    page_size: int
    items: list


class RealtimeCrawlIn(BaseModel):
    url: str = Field(min_length=8, max_length=500)


# ---------- 价格追踪 ----------

class TrackingIn(BaseModel):
    product_id: int
    target_price: Optional[float] = None


class TrackingOut(BaseModel):
    id: int
    product_id: int
    product_name: Optional[str] = None
    target_price: Optional[float] = None
    current_price: Optional[float] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TrendPoint(BaseModel):
    date: str
    price: float
    platform: str


class TrendOut(BaseModel):
    product_id: int
    product_name: str
    days: int
    points: List[TrendPoint]
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    current_price: Optional[float] = None
    avg_price: Optional[float] = None


# ---------- 价格对比 ----------

class CompareIn(BaseModel):
    product_ids: List[int] = Field(min_length=1, max_length=5)
    days: int = 180


# ---------- 系统管理 ----------

class DataSourceIn(BaseModel):
    platform: str
    name: Optional[str] = ""
    enabled: bool = True
    crawl_interval_minutes: int = 1440
    config: Optional[str] = "{}"


class ConfigIn(BaseModel):
    key: str
    value: str


class SensitiveWordIn(BaseModel):
    word: str = Field(min_length=1, max_length=64)
    category: Optional[str] = "通用"


class SensitiveWordBatchIn(BaseModel):
    words: str = Field(min_length=1, max_length=10000)  # 每行一个词
    category: Optional[str] = "通用"


# ---------- 知识库（RAG 检索增强） ----------

class KnowledgeIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    category: Optional[str] = ""
    tags: Optional[str] = ""  # 逗号分隔关键词
    content: str = Field(min_length=1, max_length=20000)
    enabled: bool = True


# ---------- 用户画像（个人中心查看/编辑） ----------

class ProfileMemoIn(BaseModel):
    content: str = Field(default="", max_length=20000)
