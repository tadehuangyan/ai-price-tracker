"""应用配置模块

集中读取 backend/.env 与环境变量中的数据库、JWT、LLM 等配置项，
供数据库连接、鉴权与 AI 服务等模块统一引用。
"""
import os
from urllib.parse import quote_plus

from dotenv import load_dotenv

# 显式加载 backend/.env（按本文件路径定位，与启动目录无关）
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

# ---------- 数据库连接配置 ----------
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "spt")

# ---------- JWT 令牌配置 ----------
JWT_SECRET = os.getenv("JWT_SECRET", "spt-dev-secret")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))

# ---------- LLM（大模型）服务配置 ----------
LLM_API_BASE = os.getenv("LLM_API_BASE", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
LLM_VISION_MODEL = os.getenv("LLM_VISION_MODEL", "")  # 多模态识图模型（OpenAI 兼容），为空回退默认

# 拼接 SQLAlchemy 连接串（PyMySQL 驱动，utf8mb4 以支持 emoji 等 4 字节字符）
# 对用户名/密码做 URL 编码，避免密码含 @ : / 等特殊字符时破坏连接串解析
DATABASE_URL = (
    f"mysql+pymysql://{quote_plus(DB_USER)}:{quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    f"?charset=utf8mb4"
)
