from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import User
from .security import decode_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="未登录")
    payload = decode_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="登录已过期，请重新登录")
    user = db.query(User).get(int(payload.get("sub", 0)))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    if user.status == "disabled":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="账号已被禁用")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return user


def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    if credentials is None:
        return None
    payload = decode_token(credentials.credentials)
    if payload is None:
        return None
    return db.query(User).get(int(payload.get("sub", 0)))
