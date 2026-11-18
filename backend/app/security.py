"""安全工具模块：bcrypt 密码哈希校验与 JWT 令牌的签发、解析"""
from datetime import datetime, timedelta

import bcrypt
from jose import JWTError, jwt

from .config import JWT_ALGORITHM, JWT_EXPIRE_MINUTES, JWT_SECRET


def hash_password(password: str) -> str:
    """对明文密码做 bcrypt 哈希（内置随机盐），返回哈希字符串"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """校验明文密码与哈希是否匹配；异常（如哈希格式非法）一律视为不匹配"""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


def create_token(user_id: int, role: str) -> str:
    """签发 JWT：sub 为用户 id、role 为角色，有效期 JWT_EXPIRE_MINUTES 分钟"""
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": datetime.utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str):
    """解析并校验 JWT 签名与有效期，无效或过期返回 None"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        return None
