import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import get_db  # noqa: E402
from app.security import generate_password, hash_password  # noqa: E402

USERNAME_RE = re.compile(r"^[a-z0-9_.]{3,32}$")


def main():
    username = (sys.argv[1] if len(sys.argv) > 1 else "superadmin").strip().lower()
    password = sys.argv[2] if len(sys.argv) > 2 else generate_password(14)
    full_name = sys.argv[3] if len(sys.argv) > 3 else "Super Administrator"

    if not USERNAME_RE.match(username):
        print("Login noto'g'ri: faqat kichik lotin harflari, raqam, '.', '_' va 3-32 belgi bo'lishi kerak.")
        sys.exit(1)

    db = get_db()
    password_hash = hash_password(password)
    existing = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

    if existing:
        db.execute(
            "UPDATE users SET password_hash = ?, role = 'admin', is_active = 1 WHERE id = ?",
            (password_hash, existing["id"]),
        )
        db.commit()
        print("Mavjud foydalanuvchining paroli yangilandi.")
    else:
        db.execute(
            "INSERT INTO users (full_name, role, username, password_hash) VALUES (?, 'admin', ?, ?)",
            (full_name, username, password_hash),
        )
        db.commit()
        print("Yangi super administrator yaratildi.")

    print()
    print("================================")
    print("  Admin panel login ma'lumotlari")
    print("================================")
    print("URL:      /admin/login")
    print(f"Login:    {username}")
    print(f"Parol:    {password}")
    print("================================")
    print("Bu parol faqat shu safar ko'rsatiladi — saqlab qo'ying va birinchi kirishdan so'ng admin panel orqali almashtiring.")


if __name__ == "__main__":
    main()
