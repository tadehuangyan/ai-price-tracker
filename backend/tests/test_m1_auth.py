# -*- coding: utf-8 -*-
"""M1 用户管理 测试（auth.py / security.py / deps.py）

覆盖目标：注册、登录、个人信息维护、我的追踪、JWT 鉴权全链路的语句与条件覆盖。
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.deps import get_current_user, get_optional_user, require_admin
from app.models import User
from app.routers import auth as auth_mod
from app.security import create_token, decode_token, hash_password, verify_password

from conftest import auth_headers, make_code, make_product, make_tracking, make_user


# ================= 注册 =================

def _send_code(db, email, purpose, monkeypatch, code="123456"):
    monkeypatch.setattr(mailer.random, "randint", lambda a, b: int(code))
    ok, msg, _ = mailer.send_verification_code(db, email, purpose)
    assert ok is True
    return code


def test_register_success_with_nickname(client, db, monkeypatch):
    code = _send_code(db, "new@qq.com", "register", monkeypatch)
    r = client.post("/api/auth/register", json={
        "username": "newuser", "password": "abc12345",
        "email": "new@qq.com", "nickname": "新用户", "code": code,
    })
    assert r.status_code == 200 and r.json()["ok"] is True
    u = db.query(User).filter(User.username == "newuser").first()
    assert u is not None and u.nickname == "新用户" and u.role == "user"


def test_register_success_without_nickname_defaults_username(client, db, monkeypatch):
    # body.nickname 为空 -> nickname 取 username（nickname or username 的假分支）
    code = _send_code(db, "nick@qq.com", "register", monkeypatch)
    r = client.post("/api/auth/register", json={
        "username": "nickuser", "password": "abc12345", "email": "nick@qq.com", "code": code,
    })
    assert r.status_code == 200
    u = db.query(User).filter(User.username == "nickuser").first()
    assert u.nickname == "nickuser"


def test_register_without_or_wrong_code_400(client, db, monkeypatch):
    # 验证码校验失败分支
    r = client.post("/api/auth/register", json={
        "username": "codeuser", "password": "abc12345", "email": "code@qq.com",
    })
    assert r.status_code == 400 and "验证码" in r.json()["detail"]
    _send_code(db, "code@qq.com", "register", monkeypatch)
    r2 = client.post("/api/auth/register", json={
        "username": "codeuser", "password": "abc12345", "email": "code@qq.com", "code": "000001",
    })
    assert r2.status_code == 400


@pytest.mark.parametrize("bad_name", ["ab", "a-b", "a b", "a" * 21, "中文名"])
def test_register_username_invalid(client, bad_name):
    # auth.py L20-21：用户名格式不合法
    r = client.post("/api/auth/register", json={
        "username": bad_name, "password": "abc12345", "email": "x@qq.com",
    })
    # 21 位超长会被 schema 的 max_length 先行拦截（422），其余进业务校验（400）
    assert r.status_code in (400, 422)
    if r.status_code == 400:
        assert "用户名" in r.json()["detail"]


def test_register_password_missing_digit(client):
    # auth.py L22-23：密码缺数字
    r = client.post("/api/auth/register", json={
        "username": "pwduser1", "password": "abcdefgh", "email": "p1@qq.com",
    })
    assert r.status_code == 400 and "密码" in r.json()["detail"]


def test_register_password_missing_letter(client):
    # auth.py L22-23：密码缺字母
    r = client.post("/api/auth/register", json={
        "username": "pwduser2", "password": "12345678", "email": "p2@qq.com",
    })
    assert r.status_code == 400 and "密码" in r.json()["detail"]


def test_register_email_invalid_business_check(client, db):
    # auth.py L24-25：邮箱格式校验分支。
    # 接口层 EmailStr 会先拦截非法邮箱（422），此处直接调用视图函数覆盖业务分支。
    body = SimpleNamespace(username="mailuser", password="abc12345", email="not-an-email", nickname=None)
    with pytest.raises(HTTPException) as e:
        auth_mod.register(body, db)
    assert e.value.status_code == 400 and "邮箱" in e.value.detail


def test_register_email_invalid_schema_422(client):
    r = client.post("/api/auth/register", json={
        "username": "mailuser2", "password": "abc12345", "email": "bad-email",
    })
    assert r.status_code == 422


def test_register_username_exists(client, db):
    make_user(db, username="exists1", email="e1@qq.com")
    r = client.post("/api/auth/register", json={
        "username": "exists1", "password": "abc12345", "email": "other@qq.com",
    })
    assert r.status_code == 400 and "用户名已存在" in r.json()["detail"]


def test_register_email_exists(client, db):
    make_user(db, username="exists2", email="e2@qq.com")
    r = client.post("/api/auth/register", json={
        "username": "exists3", "password": "abc12345", "email": "e2@qq.com",
    })
    assert r.status_code == 400 and "邮箱" in r.json()["detail"]


# ================= 登录 =================

def test_login_success_by_username(client, db):
    make_user(db, username="login1", email="l1@qq.com")
    r = client.post("/api/auth/login", json={"username": "login1", "password": "pass1234"})
    assert r.status_code == 200
    data = r.json()
    assert data["role"] == "user" and data["token"] and data["user"]["username"] == "login1"


def test_login_success_by_email(client, db):
    # 登录标识同时匹配用户名/邮箱（OR 条件两侧各覆盖一次）
    make_user(db, username="login2", email="l2@qq.com")
    r = client.post("/api/auth/login", json={"username": "l2@qq.com", "password": "pass1234"})
    assert r.status_code == 200 and r.json()["user"]["username"] == "login2"


def test_login_wrong_password(client, db):
    make_user(db, username="login3", email="l3@qq.com")
    r = client.post("/api/auth/login", json={"username": "login3", "password": "wrong999"})
    assert r.status_code == 400 and "用户名或密码错误" in r.json()["detail"]


def test_login_user_not_found(client, db):
    r = client.post("/api/auth/login", json={"username": "nobody", "password": "pass1234"})
    assert r.status_code == 400 and "用户名或密码错误" in r.json()["detail"]


def test_login_disabled_account(client, db):
    make_user(db, username="login4", email="l4@qq.com", status="disabled")
    r = client.post("/api/auth/login", json={"username": "login4", "password": "pass1234"})
    assert r.status_code == 403 and "禁用" in r.json()["detail"]


# ================= 当前用户 / 鉴权依赖 =================

def test_me_ok(client, db):
    u = make_user(db, username="me1", email="me1@qq.com")
    r = client.get("/api/auth/me", headers=auth_headers(u))
    assert r.status_code == 200 and r.json()["username"] == "me1"


def test_me_without_token_401(client):
    # deps.py L16-17：无凭证
    r = client.get("/api/auth/me")
    assert r.status_code == 401 and "未登录" in r.json()["detail"]


def test_me_invalid_token_401(client):
    # deps.py L18-20：token 解析失败
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer bad.token.value"})
    assert r.status_code == 401 and "过期" in r.json()["detail"]


def test_me_token_user_missing_401(client):
    # deps.py L21-23：token 有效但用户已不存在
    token = create_token(99999, "user")
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401 and "用户不存在" in r.json()["detail"]


def test_me_disabled_after_login_403(client, db):
    # deps.py L24-25：登录后被禁用
    u = make_user(db, username="me2", email="me2@qq.com")
    headers = auth_headers(u)
    u.status = "disabled"
    db.commit()
    r = client.get("/api/auth/me", headers=headers)
    assert r.status_code == 403 and "禁用" in r.json()["detail"]


def test_require_admin_rejects_normal_user(client, db):
    # deps.py L30-31：非管理员访问管理接口
    u = make_user(db, username="me3", email="me3@qq.com")
    r = client.get("/api/admin/config", headers=auth_headers(u))
    assert r.status_code == 403 and "管理员" in r.json()["detail"]


def test_get_optional_user_three_branches(db):
    # deps.py get_optional_user：无凭证 / 无效 token / 有效 token
    from fastapi.security import HTTPAuthorizationCredentials

    assert get_optional_user(None, db) is None
    bad = HTTPAuthorizationCredentials(scheme="Bearer", credentials="bad.token")
    assert get_optional_user(bad, db) is None
    u = make_user(db, username="opt1", email="opt1@qq.com")
    good = HTTPAuthorizationCredentials(scheme="Bearer", credentials=create_token(u.id, u.role))
    got = get_optional_user(good, db)
    assert got is not None and got.id == u.id


def test_get_current_user_direct(db):
    u = make_user(db, username="dep1", email="dep1@qq.com")
    from fastapi.security import HTTPAuthorizationCredentials

    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=create_token(u.id, u.role))
    assert get_current_user(creds, db).id == u.id
    with pytest.raises(HTTPException) as e:
        get_current_user(None, db)
    assert e.value.status_code == 401


def test_require_admin_direct(db):
    admin = make_user(db, username="adm", email="adm@qq.com", role="admin")
    assert require_admin(admin).id == admin.id
    with pytest.raises(HTTPException) as e:
        require_admin(admin.__class__(username="x", role="user"))
    assert e.value.status_code == 403


# ================= 个人信息维护 =================

def test_profile_update_nickname_only(client, db):
    u = make_user(db, username="pro1", email="pro1@qq.com")
    r = client.put("/api/auth/profile", json={"nickname": "新昵称"}, headers=auth_headers(u))
    assert r.status_code == 200
    assert db.query(User).get(u.id).nickname == "新昵称"


def test_profile_update_email_change(client, db, monkeypatch):
    u = make_user(db, username="pro2", email="pro2@qq.com")
    code = _send_code(db, "pro2new@qq.com", "email_change", monkeypatch)
    r = client.put("/api/auth/profile", json={"email": "pro2new@qq.com", "email_code": code},
                   headers=auth_headers(u))
    assert r.status_code == 200
    assert db.query(User).get(u.id).email == "pro2new@qq.com"
    # 换绑成功向旧邮箱发通知
    from app.models import MailMessage
    m = db.query(MailMessage).filter(MailMessage.category == "system").first()
    assert m.to_email == "pro2@qq.com" and "邮箱换绑" in m.subject


def test_profile_update_email_wrong_code_400(client, db, monkeypatch):
    u = make_user(db, username="pro2b", email="pro2b@qq.com")
    _send_code(db, "pro2bnew@qq.com", "email_change", monkeypatch)
    r = client.put("/api/auth/profile", json={"email": "pro2bnew@qq.com", "email_code": "000001"},
                   headers=auth_headers(u))
    assert r.status_code == 400 and "验证码" in r.json()["detail"]
    assert db.query(User).get(u.id).email == "pro2b@qq.com"


def test_profile_update_email_same_skipped(client, db):
    # body.email == user.email -> 不查重不修改
    u = make_user(db, username="pro3", email="pro3@qq.com")
    r = client.put("/api/auth/profile", json={"email": "pro3@qq.com"}, headers=auth_headers(u))
    assert r.status_code == 200


def test_profile_update_email_exists_400(client, db):
    make_user(db, username="pro4a", email="taken@qq.com")
    u = make_user(db, username="pro4b", email="pro4b@qq.com")
    r = client.put("/api/auth/profile", json={"email": "taken@qq.com"}, headers=auth_headers(u))
    assert r.status_code == 400 and "邮箱已被注册" in r.json()["detail"]


def test_profile_update_password_ok(client, db, monkeypatch):
    u = make_user(db, username="pro5", email="pro5@qq.com")
    code = _send_code(db, "pro5@qq.com", "password_change", monkeypatch)
    r = client.put("/api/auth/profile", json={"password": "newpass99", "password_code": code},
                   headers=auth_headers(u))
    assert r.status_code == 200
    assert verify_password("newpass99", db.query(User).get(u.id).password_hash)
    r2 = client.post("/api/auth/login", json={"username": "pro5", "password": "newpass99"})
    assert r2.status_code == 200
    # 修改成功向绑定邮箱发通知
    from app.models import MailMessage
    m = db.query(MailMessage).filter(MailMessage.category == "system").first()
    assert m.to_email == "pro5@qq.com" and "密码修改" in m.subject


def test_profile_update_password_wrong_code_400(client, db, monkeypatch):
    u = make_user(db, username="pro5b", email="pro5b@qq.com")
    _send_code(db, "pro5b@qq.com", "password_change", monkeypatch)
    r = client.put("/api/auth/profile", json={"password": "newpass99", "password_code": "000001"},
                   headers=auth_headers(u))
    assert r.status_code == 400 and "验证码" in r.json()["detail"]


def test_profile_update_password_invalid_charset(client, db):
    # 密码含字母数字条件为假 -> 400
    u = make_user(db, username="pro6", email="pro6@qq.com")
    for bad in ("12345678", "abcdefgh"):
        r = client.put("/api/auth/profile", json={"password": bad}, headers=auth_headers(u))
        assert r.status_code == 400


def test_profile_update_password_too_short(client, db):
    # 含字母数字但长度 < 8 -> 400（len 条件为真）
    u = make_user(db, username="pro7", email="pro7@qq.com")
    r = client.put("/api/auth/profile", json={"password": "ab1"}, headers=auth_headers(u))
    assert r.status_code == 400


def test_profile_update_password_empty_skipped(client, db):
    # body.password 为空 -> 不改密码
    u = make_user(db, username="pro8", email="pro8@qq.com")
    r = client.put("/api/auth/profile", json={"password": ""}, headers=auth_headers(u))
    assert r.status_code == 200
    assert verify_password("pass1234", db.query(User).get(u.id).password_hash)


def test_profile_update_nothing(client, db):
    u = make_user(db, username="pro9", email="pro9@qq.com")
    r = client.put("/api/auth/profile", json={}, headers=auth_headers(u))
    assert r.status_code == 200


# ================= 我的追踪 =================

def test_my_trackings_ok(client, db):
    u = make_user(db, username="trk1", email="trk1@qq.com")
    p = make_product(db)
    make_tracking(db, u, p, target_price=99.0)
    r = client.get("/api/auth/my-trackings", headers=auth_headers(u))
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1 and items[0]["product_name"] == p.name
    assert items[0]["target_price"] == 99.0 and items[0]["created_at"] is not None


def test_my_trackings_created_at_none(client, db):
    # created_at 为空 -> 返回 None 的条件分支
    u = make_user(db, username="trk2", email="trk2@qq.com")
    p = make_product(db)
    from conftest import make_tracking as mt
    t = mt(db, u, p, target_price=None)
    t.created_at = None
    db.commit()
    r = client.get("/api/auth/my-trackings", headers=auth_headers(u))
    assert r.status_code == 200 and r.json()[0]["created_at"] is None


def test_my_trackings_empty(client, db):
    u = make_user(db, username="trk3", email="trk3@qq.com")
    r = client.get("/api/auth/my-trackings", headers=auth_headers(u))
    assert r.status_code == 200 and r.json() == []


# ================= security.py 单元 =================

def test_hash_and_verify_password_roundtrip():
    h = hash_password("secret123")
    assert verify_password("secret123", h) is True
    assert verify_password("other456", h) is False


def test_verify_password_invalid_hash_returns_false():
    # 异常分支：非法 bcrypt 哈希
    assert verify_password("secret123", "not-a-bcrypt-hash") is False


def test_create_and_decode_token_roundtrip():
    token = create_token(42, "admin")
    payload = decode_token(token)
    assert payload["sub"] == "42" and payload["role"] == "admin"
    assert decode_token("invalid.token") is None


# ================= 模拟邮箱服务（mailer.py） =================

from app.services import mailer


def test_send_verification_code_and_rate_limit(db, monkeypatch):
    monkeypatch.setattr(mailer.random, "randint", lambda a, b: 123456)
    ok, msg, code = mailer.send_verification_code(db, "v@qq.com", "register")
    assert ok is True and code == "123456" and "模拟投递" in msg
    # 60 秒内重发 -> 频率限制分支
    ok2, msg2, code2 = mailer.send_verification_code(db, "v@qq.com", "register")
    assert ok2 is False and "60 秒" in msg2 and code2 == ""
    # 不同用途不受限制；未知 purpose 使用原值
    ok3, _, _ = mailer.send_verification_code(db, "v@qq.com", "other_purpose", user_id=1)
    assert ok3 is True


def test_check_verification_code_branches(db, monkeypatch):
    monkeypatch.setattr(mailer.random, "randint", lambda a, b: 654321)
    mailer.send_verification_code(db, "c@qq.com", "password_change")
    # 空验证码 -> False 分支
    assert mailer.check_verification_code(db, "c@qq.com", "password_change", "") is False
    # 错误验证码 -> 查询无结果分支
    assert mailer.check_verification_code(db, "c@qq.com", "password_change", "000001") is False
    # consume=False -> 不作废的分支
    assert mailer.check_verification_code(db, "c@qq.com", "password_change", "654321", consume=False) is True
    assert mailer.check_verification_code(db, "c@qq.com", "password_change", "654321", consume=False) is True
    # 正确验证码 -> 通过并作废
    assert mailer.check_verification_code(db, "c@qq.com", "password_change", "654321") is True
    assert mailer.check_verification_code(db, "c@qq.com", "password_change", "654321") is False  # 已使用
    # 过期验证码（未使用）-> 有效期过滤分支
    m1 = db.query(mailer.MailMessage).first()
    m1.created_at = datetime.now() - timedelta(seconds=120)  # 回拨以规避重发限制
    db.commit()
    mailer.send_verification_code(db, "c@qq.com", "password_change")
    m2 = db.query(mailer.MailMessage).order_by(mailer.MailMessage.id.desc()).first()
    m2.created_at = datetime.now() - timedelta(seconds=mailer.CODE_TTL_SECONDS + 60)
    db.commit()
    assert mailer.check_verification_code(db, "c@qq.com", "password_change", "654321") is False


def test_mail_to_dict_and_category_fallback(db):
    from app.models import MailMessage

    m1 = MailMessage(user_id=1, to_email="m@qq.com", category="price_alert",
                     subject="降价", body="内容", code="", status="sent")
    m2 = MailMessage(to_email="m@qq.com", category="unknown_cat", subject="s", body="b")
    db.add_all([m1, m2])
    db.commit()
    d1 = mailer.mail_to_dict(m1)
    assert d1["category_name"] == "降价提醒" and d1["created_at"] is not None
    # 未知分类回退原值；created_at 为空 -> None 分支
    m2.created_at = None
    db.commit()
    d2 = mailer.mail_to_dict(db.query(MailMessage).get(m2.id))
    assert d2["category_name"] == "unknown_cat" and d2["created_at"] is None
