import secrets
import time

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel

from app import telegram_bot
from app.db import get_db
from app.deps import get_current_user
from app.security import clear_session, issue_session, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 15 * 60
_login_attempts: dict[str, dict] = {}


def _is_locked_out(key: str) -> bool:
    entry = _login_attempts.get(key)
    if not entry:
        return False
    if time.time() - entry["first_attempt_at"] > LOGIN_LOCKOUT_SECONDS:
        _login_attempts.pop(key, None)
        return False
    return entry["count"] >= MAX_LOGIN_ATTEMPTS


def _record_failed_attempt(key: str):
    entry = _login_attempts.get(key)
    if not entry or time.time() - entry["first_attempt_at"] > LOGIN_LOCKOUT_SECONDS:
        _login_attempts[key] = {"count": 1, "first_attempt_at": time.time()}
    else:
        entry["count"] += 1


def _clear_attempts(key: str):
    _login_attempts.pop(key, None)


def _public_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "fullName": user["full_name"],
        "role": user["role"],
        "orgId": user["org_id"],
        "telegramLinked": bool(user["telegram_chat_id"]),
    }


class ExchangeBody(BaseModel):
    token: str


class DevVerifyBody(BaseModel):
    token: str
    userId: int


class AdminLoginBody(BaseModel):
    username: str
    password: str


@router.post("/telegram/start")
def telegram_start():
    token = secrets.token_hex(20)
    db = get_db()
    db.execute(
        "INSERT INTO login_tokens (token, status, expires_at) VALUES (?, 'pending', datetime('now', '+10 minutes'))",
        (token,),
    )
    db.commit()
    return {
        "token": token,
        "deepLink": telegram_bot.login_deep_link(token),
        "botConfigured": telegram_bot.is_configured(),
    }


@router.get("/telegram/status/{token}")
def telegram_status(token: str):
    db = get_db()
    row = db.execute("SELECT * FROM login_tokens WHERE token = ?", (token,)).fetchone()
    if not row:
        return {"status": "expired"}
    from datetime import datetime

    if row["status"] == "pending" and datetime.fromisoformat(row["expires_at"]) < datetime.utcnow():
        return {"status": "expired"}
    return {"status": row["status"]}


@router.post("/telegram/exchange")
def telegram_exchange(body: ExchangeBody, response: Response):
    db = get_db()
    row = db.execute("SELECT * FROM login_tokens WHERE token = ? AND status = 'verified'", (body.token,)).fetchone()
    if not row:
        raise HTTPException(status_code=400, detail="Token tasdiqlanmagan")

    user_row = db.execute("SELECT * FROM users WHERE id = ? AND is_active = 1", (row["user_id"],)).fetchone()
    if not user_row:
        raise HTTPException(status_code=400, detail="Foydalanuvchi topilmadi")
    user = dict(user_row)

    db.execute("UPDATE login_tokens SET status = 'consumed' WHERE token = ?", (body.token,))
    db.commit()
    issue_session(response, user["id"])
    return {"user": _public_user(user)}


# Dev-only convenience: lets you test the whole flow without a real Telegram bot.
# Only active while BOT_TOKEN is unset, so it can never work in a configured deployment.
@router.get("/dev/users")
def dev_users():
    if telegram_bot.is_configured():
        raise HTTPException(status_code=404)
    db = get_db()
    rows = db.execute("SELECT id, full_name, role FROM users WHERE is_active = 1 ORDER BY role, full_name").fetchall()
    return [{"id": r["id"], "fullName": r["full_name"], "role": r["role"]} for r in rows]


@router.post("/dev/verify")
def dev_verify(body: DevVerifyBody):
    if telegram_bot.is_configured():
        raise HTTPException(status_code=404)
    db = get_db()
    row = db.execute("SELECT * FROM login_tokens WHERE token = ? AND status = 'pending'", (body.token,)).fetchone()
    if not row:
        raise HTTPException(status_code=400, detail="Token topilmadi")
    user = db.execute("SELECT * FROM users WHERE id = ?", (body.userId,)).fetchone()
    if not user:
        raise HTTPException(status_code=400, detail="Foydalanuvchi topilmadi")
    db.execute("UPDATE login_tokens SET status = 'verified', user_id = ? WHERE token = ?", (user["id"], body.token))
    db.commit()
    return {"ok": True}


@router.post("/admin-login")
def admin_login(body: AdminLoginBody, response: Response):
    clean_username = body.username.strip().lower()
    if not clean_username or not body.password:
        raise HTTPException(status_code=400, detail="Login va parol kiritilishi shart")

    if _is_locked_out(clean_username):
        raise HTTPException(status_code=429, detail="Juda ko'p noto'g'ri urinish. 15 daqiqadan so'ng qayta urining.")

    db = get_db()
    row = db.execute(
        "SELECT * FROM users WHERE username = ? AND role = 'admin' AND is_active = 1", (clean_username,)
    ).fetchone()
    if not row or not verify_password(body.password, row["password_hash"]):
        _record_failed_attempt(clean_username)
        raise HTTPException(status_code=401, detail="Login yoki parol noto'g'ri")

    user = dict(row)
    _clear_attempts(clean_username)
    issue_session(response, user["id"])
    return {"user": _public_user(user)}


@router.get("/me")
def me(current_user: dict = Depends(get_current_user)):
    return {"user": _public_user(current_user)}


@router.post("/logout")
def logout(response: Response):
    clear_session(response)
    return {"ok": True}
