from fastapi import Cookie, Depends, HTTPException, Response, status

from app.db import get_db
from app.security import COOKIE_NAME, issue_session, verify_session_token


def get_current_user(response: Response, session: str | None = Cookie(default=None, alias=COOKIE_NAME)) -> dict:
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Tizimga kirilmagan")

    user_id = verify_session_token(session)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessiya yaroqsiz")

    db = get_db()
    row = db.execute("SELECT * FROM users WHERE id = ? AND is_active = 1", (user_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Foydalanuvchi topilmadi")

    user = dict(row)
    # Sliding expiry: every authenticated request pushes the session further out.
    issue_session(response, user["id"])
    return user


def require_roles(*roles: str):
    def checker(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user["role"] not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Ruxsat yo'q")
        return current_user

    return checker
