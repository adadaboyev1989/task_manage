import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import get_db  # noqa: E402


def ensure_department():
    db = get_db()
    existing = db.execute("SELECT * FROM users WHERE role = 'department' LIMIT 1").fetchone()
    if existing:
        return dict(existing)
    cur = db.execute(
        "INSERT INTO users (full_name, role, phone) VALUES (?, 'department', ?)", ("Bo'lim mutaxassisi", "+998901111111")
    )
    db.commit()
    return dict(db.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone())


def ensure_org_with_director(name: str, org_type: str, full_name: str):
    db = get_db()
    org = db.execute("SELECT * FROM orgs WHERE name = ?", (name,)).fetchone()
    if not org:
        cur = db.execute("INSERT INTO orgs (name, type) VALUES (?, ?)", (name, org_type))
        db.commit()
        org = db.execute("SELECT * FROM orgs WHERE id = ?", (cur.lastrowid,)).fetchone()
    org = dict(org)

    if not org["director_user_id"]:
        cur = db.execute("INSERT INTO users (full_name, role, org_id) VALUES (?, 'director', ?)", (full_name, org["id"]))
        db.execute("UPDATE orgs SET director_user_id = ? WHERE id = ?", (cur.lastrowid, org["id"]))
        db.commit()

    return dict(db.execute("SELECT * FROM orgs WHERE id = ?", (org["id"],)).fetchone())


def main():
    ensure_department()
    ensure_org_with_director("20-maktab", "school", "Aliyev Vali")
    ensure_org_with_director("5-bog'cha", "kindergarten", "Karimova Nodira")

    print("Seed tayyor.")
    print(
        "Diqqat: seedlangan foydalanuvchilarning Telegram ID'si hali kiritilmagan — /admin panelidan har biriga "
        "Telegram ID biriktiring (foydalanuvchi botga /start yozganda o'z ID'sini ko'radi)."
    )
    print("Administrator hisobi uchun: python scripts/create_superadmin.py")


if __name__ == "__main__":
    main()
