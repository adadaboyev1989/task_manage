import hashlib
import os
import secrets
import string
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Response

from app.config import ENVIRONMENT, JWT_SECRET

COOKIE_NAME = "session"
# Browsers cap cookie Max-Age at 400 days (Chrome/Safari) — effectively "stay logged
# in forever" as long as the device opens the app at least once in that window, since
# require_auth slides the expiry forward on every authenticated request.
SESSION_DAYS = 400
SESSION_SECONDS = SESSION_DAYS * 24 * 60 * 60

_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_KEY_LEN = 64


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt.encode("utf-8"), n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_KEY_LEN
    )
    return f"{salt}:{digest.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored or ":" not in stored:
        return False
    salt, hex_hash = stored.split(":", 1)
    candidate = hashlib.scrypt(
        password.encode("utf-8"), salt=salt.encode("utf-8"), n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_KEY_LEN
    )
    expected = bytes.fromhex(hex_hash)
    if len(candidate) != len(expected):
        return False
    return secrets.compare_digest(candidate, expected)


def generate_password(length: int = 14) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def issue_session(response: Response, user_id: int) -> None:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(seconds=SESSION_SECONDS),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=SESSION_SECONDS,
        httponly=True,
        samesite="lax",
        secure=(ENVIRONMENT == "production"),
        path="/",
    )


def clear_session(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


def verify_session_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return int(payload["sub"])
    except jwt.PyJWTError:
        return None
