import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.db import get_db
from app.deps import require_roles
from app.security import hash_password

router = APIRouter(prefix="/api/users", tags=["users"], dependencies=[Depends(require_roles("admin"))])

TELEGRAM_ID_RE = re.compile(r"^\d{5,15}$")
USERNAME_RE = re.compile(r"^[a-z0-9_.]{3,32}$")


class CreateUserBody(BaseModel):
    fullName: str
    role: str
    phone: str = ""
    orgId: Optional[int] = None
    telegramId: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None


class UpdateUserBody(BaseModel):
    fullName: Optional[str] = None
    phone: Optional[str] = None
    isActive: Optional[bool] = None
    orgId: Optional[int] = None
    telegramId: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None


def _public_user(u: dict) -> dict:
    return {
        "id": u["id"],
        "fullName": u["full_name"],
        "role": u["role"],
        "phone": u["phone"],
        "orgId": u["org_id"],
        "orgName": u.get("org_name"),
        "telegramChatId": u["telegram_chat_id"],
        "telegramLinked": bool(u["telegram_chat_id"]),
        "telegramUsername": u["telegram_username"],
        "username": u["username"],
        "hasPassword": bool(u["password_hash"]),
        "isActive": bool(u["is_active"]),
        "createdAt": u["created_at"],
    }


def _user_with_org(db, user_id: int) -> dict:
    row = db.execute(
        "SELECT u.*, o.name AS org_name FROM users u LEFT JOIN orgs o ON o.id = u.org_id WHERE u.id = ?", (user_id,)
    ).fetchone()
    return dict(row)


@router.get("")
def list_users(role: Optional[str] = None):
    db = get_db()
    if role:
        rows = db.execute(
            "SELECT u.*, o.name AS org_name FROM users u LEFT JOIN orgs o ON o.id = u.org_id WHERE u.role = ? ORDER BY u.created_at DESC",
            (role,),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT u.*, o.name AS org_name FROM users u LEFT JOIN orgs o ON o.id = u.org_id ORDER BY u.created_at DESC"
        ).fetchall()
    return [_public_user(dict(r)) for r in rows]


@router.post("", status_code=201)
def create_user(body: CreateUserBody):
    db = get_db()

    if not body.fullName.strip():
        raise HTTPException(status_code=400, detail="Ism kiritilishi shart")
    if body.role not in ("admin", "department", "director"):
        raise HTTPException(status_code=400, detail="Rol noto'g'ri")

    wants_telegram = bool(body.telegramId and body.telegramId.strip())
    clean_telegram_id = None
    if wants_telegram:
        clean_telegram_id = body.telegramId.strip()
        if not TELEGRAM_ID_RE.match(clean_telegram_id):
            raise HTTPException(
                status_code=400, detail="Telegram ID noto'g'ri. Foydalanuvchi botga /start yozganda o'z ID'sini ko'radi."
            )
        if db.execute("SELECT 1 FROM users WHERE telegram_chat_id = ?", (clean_telegram_id,)).fetchone():
            raise HTTPException(status_code=400, detail="Bu Telegram ID allaqachon boshqa foydalanuvchiga biriktirilgan")
    elif body.role != "admin":
        raise HTTPException(status_code=400, detail="Telegram ID kiritilishi shart")

    clean_username = None
    password_hash = None
    wants_password = bool(body.username or body.password)
    if wants_password:
        if body.role != "admin":
            raise HTTPException(status_code=400, detail="Login-parol faqat administrator uchun")
        clean_username = (body.username or "").strip().lower()
        if not USERNAME_RE.match(clean_username):
            raise HTTPException(status_code=400, detail="Login 3-32 belgi, faqat kichik lotin harflari/raqam/._ bo'lishi kerak")
        if not body.password or len(body.password) < 6:
            raise HTTPException(status_code=400, detail="Parol kamida 6 belgidan iborat bo'lishi kerak")
        if db.execute("SELECT 1 FROM users WHERE username = ?", (clean_username,)).fetchone():
            raise HTTPException(status_code=400, detail="Bu login allaqachon band")
        password_hash = hash_password(body.password)

    if body.role == "admin" and not wants_telegram and not wants_password:
        raise HTTPException(status_code=400, detail="Administrator uchun Telegram ID yoki login-parol kiritilishi shart")

    if body.role == "director":
        if not body.orgId:
            raise HTTPException(status_code=400, detail="Direktor uchun tashkilot tanlanishi shart")
        org = db.execute("SELECT * FROM orgs WHERE id = ?", (body.orgId,)).fetchone()
        if not org:
            raise HTTPException(status_code=400, detail="Tashkilot topilmadi")
        if org["director_user_id"]:
            raise HTTPException(status_code=400, detail="Bu tashkilotda allaqachon direktor bor")

    cur = db.execute(
        """INSERT INTO users (full_name, role, phone, org_id, telegram_chat_id, username, password_hash)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            body.fullName.strip(),
            body.role,
            body.phone.strip(),
            body.orgId if body.role == "director" else None,
            clean_telegram_id,
            clean_username,
            password_hash,
        ),
    )
    user_id = cur.lastrowid

    if body.role == "director":
        db.execute("UPDATE orgs SET director_user_id = ? WHERE id = ?", (user_id, body.orgId))

    db.commit()
    return _public_user(_user_with_org(db, user_id))


@router.patch("/{user_id}")
def update_user(user_id: int, body: UpdateUserBody):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="Topilmadi")
    user = dict(user)

    if body.telegramId is not None:
        clean_telegram_id = body.telegramId.strip()
        if not TELEGRAM_ID_RE.match(clean_telegram_id):
            raise HTTPException(status_code=400, detail="Telegram ID noto'g'ri")
        clash = db.execute(
            "SELECT 1 FROM users WHERE telegram_chat_id = ? AND id != ?", (clean_telegram_id, user_id)
        ).fetchone()
        if clash:
            raise HTTPException(status_code=400, detail="Bu Telegram ID allaqachon boshqa foydalanuvchiga biriktirilgan")
        db.execute("UPDATE users SET telegram_chat_id = ?, telegram_username = NULL WHERE id = ?", (clean_telegram_id, user_id))

    if body.username is not None or body.password is not None:
        if user["role"] != "admin":
            raise HTTPException(status_code=400, detail="Login-parol faqat administrator uchun")

        if body.username is not None:
            clean_username = body.username.strip().lower()
            if not USERNAME_RE.match(clean_username):
                raise HTTPException(status_code=400, detail="Login 3-32 belgi, faqat kichik lotin harflari/raqam/._ bo'lishi kerak")
            clash = db.execute("SELECT 1 FROM users WHERE username = ? AND id != ?", (clean_username, user_id)).fetchone()
            if clash:
                raise HTTPException(status_code=400, detail="Bu login allaqachon band")
            db.execute("UPDATE users SET username = ? WHERE id = ?", (clean_username, user_id))

        if body.password is not None:
            if not body.password or len(body.password) < 6:
                raise HTTPException(status_code=400, detail="Parol kamida 6 belgidan iborat bo'lishi kerak")
            db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(body.password), user_id))

    if body.orgId is not None and user["role"] == "director" and body.orgId != user["org_id"]:
        org = db.execute("SELECT * FROM orgs WHERE id = ?", (body.orgId,)).fetchone()
        if not org:
            raise HTTPException(status_code=400, detail="Tashkilot topilmadi")
        if org["director_user_id"] and org["director_user_id"] != user_id:
            raise HTTPException(status_code=400, detail="Bu tashkilotda allaqachon direktor bor")
        db.execute("UPDATE orgs SET director_user_id = NULL WHERE director_user_id = ?", (user_id,))
        db.execute("UPDATE orgs SET director_user_id = ? WHERE id = ?", (user_id, body.orgId))
        db.execute("UPDATE users SET org_id = ? WHERE id = ?", (body.orgId, user_id))

    db.execute(
        "UPDATE users SET full_name = COALESCE(?, full_name), phone = COALESCE(?, phone), is_active = COALESCE(?, is_active) WHERE id = ?",
        (
            body.fullName.strip() if body.fullName is not None else None,
            body.phone.strip() if body.phone is not None else None,
            (1 if body.isActive else 0) if body.isActive is not None else None,
            user_id,
        ),
    )
    db.commit()
    return _public_user(_user_with_org(db, user_id))


@router.delete("/{user_id}")
def delete_user(user_id: int, current_user: dict = Depends(require_roles("admin"))):
    if user_id == current_user["id"]:
        raise HTTPException(status_code=400, detail="O'zingizni o'chira olmaysiz")

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="Topilmadi")

    has_activity = (
        db.execute("SELECT 1 FROM tasks WHERE created_by = ? LIMIT 1", (user_id,)).fetchone()
        or db.execute("SELECT 1 FROM attachments WHERE uploaded_by = ? LIMIT 1", (user_id,)).fetchone()
        or db.execute("SELECT 1 FROM task_targets WHERE completed_by = ? LIMIT 1", (user_id,)).fetchone()
    )
    if has_activity:
        raise HTTPException(
            status_code=400,
            detail="Bu foydalanuvchi bilan bog'liq topshiriqlar yoki fayllar mavjud, shuning uchun o'chirib bo'lmaydi. Uni bloklashingiz mumkin.",
        )

    db.execute("UPDATE orgs SET director_user_id = NULL WHERE director_user_id = ?", (user_id,))
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()
    return {"ok": True}
