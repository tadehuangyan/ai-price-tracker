import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Product, Tracking, User
from ..schemas import LoginIn, ProfileUpdate, RegisterIn, UserOut
from ..security import create_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["用户管理"])

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@router.post("/register")
def register(body: RegisterIn, db: Session = Depends(get_db)):
    """REQ-SPT-101 用户注册：用户名 3~20 位且唯一，密码 >=8 位含字母数字，邮箱格式校验"""
    if not re.match(r"^[A-Za-z0-9_]{3,20}$", body.username):
        raise HTTPException(400, "用户名须为 3~20 位字母、数字或下划线")
    if not (re.search(r"[A-Za-z]", body.password) and re.search(r"\d", body.password)):
        raise HTTPException(400, "密码不少于 8 位且须同时包含字母与数字")
    if not EMAIL_RE.match(body.email):
        raise HTTPException(400, "邮箱格式不正确")
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(400, "用户名已存在")
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(400, "该邮箱已被注册")

    user = User(
        username=body.username,
        email=body.email,
        nickname=body.nickname or body.username,
        password_hash=hash_password(body.password),
        role="user",
    )
    db.add(user)
    db.commit()
    return {"ok": True, "message": "注册成功"}


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    """REQ-SPT-102 登录：用户名或邮箱 + 密码，成功返回 JWT 与角色"""
    user = (
        db.query(User)
        .filter((User.username == body.username) | (User.email == body.username))
        .first()
    )
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(400, "用户名或密码错误")
    if user.status == "disabled":
        raise HTTPException(403, "账号已被禁用，请联系管理员")
    token = create_token(user.id, user.role)
    return {
        "token": token,
        "role": user.role,
        "user": UserOut.model_validate(user).model_dump(mode="json"),
    }


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return UserOut.model_validate(user).model_dump(mode="json")


@router.put("/profile")
def update_profile(
    body: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """REQ-SPT-103 个人信息管理"""
    if body.nickname is not None:
        user.nickname = body.nickname
    if body.email is not None and body.email != user.email:
        if db.query(User).filter(User.email == body.email).first():
            raise HTTPException(400, "该邮箱已被注册")
        user.email = body.email
    if body.password:
        if not (re.search(r"[A-Za-z]", body.password) and re.search(r"\d", body.password)) or len(body.password) < 8:
            raise HTTPException(400, "密码不少于 8 位且须同时包含字母与数字")
        user.password_hash = hash_password(body.password)
    db.commit()
    return {"ok": True, "message": "修改成功"}


@router.get("/my-trackings")
def my_trackings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """REQ-SPT-103 查看自身订阅的追踪商品"""
    rows = (
        db.query(Tracking, Product)
        .join(Product, Tracking.product_id == Product.id)
        .filter(Tracking.user_id == user.id)
        .order_by(Tracking.created_at.desc())
        .all()
    )
    return [
        {
            "id": t.id,
            "product_id": t.product_id,
            "product_name": p.name,
            "target_price": t.target_price,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t, p in rows
    ]
