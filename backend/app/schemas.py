"""Pydantic 请求/响应模型定义

按业务域划分：用户管理、商品查询、价格追踪、价格对比、系统管理与知识库等，
用于接口参数校验与出参序列化。
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


# ---------- 用户管理 ----------

class RegisterIn(BaseModel):
    """用户注册入参：用户名、密码、邮箱与可选的模拟邮箱验证码"""
    username: str = Field(min_length=3, max_length=20)
    password: str = Field(min_length=8, max_length=64)
    email: EmailStr
    nickname: Optional[str] = None
    code: Optional[str] = None  # 模拟邮箱验证码


class LoginIn(BaseModel):
    """登录入参：用户名或邮箱 + 密码，remember 预留记住登录"""
    username: str
    password: str
    remember: bool = False


class ProfileUpdate(BaseModel):
    """个人信息修改入参：昵称/换绑邮箱/改密（后两者需配套验证码）"""
    nickname: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    email_code: Optional[str] = None  # 换绑邮箱验证码
    password_code: Optional[str] = None  # 修改密码验证码


class SendCodeIn(BaseModel):
    """发送验证码入参：目标邮箱 + 用途（注册/换绑邮箱/修改密码）"""
    email: EmailStr
    purpose: str = Field(pattern="^(register|email_change|password_change)$")


class VerifyCodeIn(SendCodeIn):
    """校验验证码入参：在发送入参基础上追加 6 位验证码"""
    code: str = Field(min_length=6, max_length=6)


class UserOut(BaseModel):
    """用户出参：对外暴露的用户信息（不含密码哈希）"""
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
    """平台报价出参：某商品在某平台的在售链接与当前价"""
    id: int
    platform: str
    url: str
    title: str
    current_price: float
    last_crawled_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ProductOut(BaseModel):
    """商品出参：基本信息 + 最低价与各平台报价列表"""
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
    """通用分页出参：total/page/page_size + 当前页数据"""
    total: int
    page: int
    page_size: int
    items: list


class RealtimeCrawlIn(BaseModel):
    """实时采集入参：待抓取的商品详情页链接"""
    url: str = Field(min_length=8, max_length=500)


# ---------- 价格追踪 ----------

class TrackingIn(BaseModel):
    """添加价格追踪入参：商品 id 与可选目标价"""
    product_id: int
    target_price: Optional[float] = None


class TrackingOut(BaseModel):
    """追踪记录出参：商品、目标价与当前价"""
    id: int
    product_id: int
    product_name: Optional[str] = None
    target_price: Optional[float] = None
    current_price: Optional[float] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TrendPoint(BaseModel):
    """价格走势单点：日期 + 当日最低价 + 来源平台"""
    date: str
    price: float
    platform: str


class TrendOut(BaseModel):
    """价格走势出参：序列点 + 最高/最低/当前/均价统计"""
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
    """比价入参：1~5 个商品 id + 回看天数"""
    product_ids: List[int] = Field(min_length=1, max_length=5)
    days: int = 180


# ---------- 系统管理 ----------

class DataSourceIn(BaseModel):
    """数据源配置入参：平台标识、名称、启用状态与采集频率"""
    platform: str
    name: Optional[str] = ""
    enabled: bool = True
    crawl_interval_minutes: int = 1440
    config: Optional[str] = "{}"


class ConfigIn(BaseModel):
    """系统配置入参：键值对更新"""
    key: str
    value: str


class SensitiveWordIn(BaseModel):
    """单个敏感词入参：词 + 分类"""
    word: str = Field(min_length=1, max_length=64)
    category: Optional[str] = "通用"


class SensitiveWordBatchIn(BaseModel):
    """批量导入敏感词入参：多行文本（每行一个词）+ 分类"""
    words: str = Field(min_length=1, max_length=10000)  # 每行一个词
    category: Optional[str] = "通用"


# ---------- 知识库（RAG 检索增强） ----------

class KnowledgeIn(BaseModel):
    """知识库条目入参：标题、分类、标签、正文与启用状态"""
    title: str = Field(min_length=1, max_length=255)
    category: Optional[str] = ""
    tags: Optional[str] = ""  # 逗号分隔关键词
    content: str = Field(min_length=1, max_length=20000)
    enabled: bool = True


# ---------- 用户画像（个人中心查看/编辑） ----------

class ProfileMemoIn(BaseModel):
    """用户画像备注入参：整文覆盖保存的 Markdown 内容"""
    content: str = Field(default="", max_length=20000)
