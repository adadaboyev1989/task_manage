from pydantic import BaseModel

from fastapi import APIRouter, Depends
from app.config import UPLOAD_DIR
from app.db import get_db
from app.deps import require_roles

router = APIRouter(prefix="/api/admin", tags=["maintenance"], dependencies=[Depends(require_roles("admin"))])


class CleanupBody(BaseModel):
    olderThanDays: int = 90


def _eligible_attachments(db, older_than_days: int):
    return db.execute(
        """SELECT a.id, a.stored_name, a.size FROM attachments a
           JOIN tasks t ON t.id = a.task_id
           WHERE a.stored_name IS NOT NULL
             AND a.created_at < datetime('now', ?)
             AND NOT EXISTS (
               SELECT 1 FROM task_targets tt WHERE tt.task_id = t.id AND tt.status IN ('pending','sent')
             )""",
        (f"-{older_than_days} days",),
    ).fetchall()


@router.get("/storage")
def storage_stats():
    db = get_db()
    total = db.execute("SELECT COUNT(*) c, COALESCE(SUM(size),0) s FROM attachments WHERE stored_name IS NOT NULL").fetchone()
    eligible = _eligible_attachments(db, 90)
    eligible_size = sum(r["size"] or 0 for r in eligible)
    return {
        "fileCount": total["c"],
        "totalSizeBytes": total["s"],
        "cleanupEligibleCount": len(eligible),
        "cleanupEligibleSizeBytes": eligible_size,
    }


@router.post("/cleanup-files")
def cleanup_files(body: CleanupBody):
    days = max(0, body.olderThanDays)
    db = get_db()
    rows = _eligible_attachments(db, days)

    deleted_count = 0
    freed_bytes = 0
    for row in rows:
        path = UPLOAD_DIR / row["stored_name"]
        try:
            if path.exists():
                freed_bytes += path.stat().st_size
                path.unlink()
        except OSError:
            pass
        db.execute("DELETE FROM attachments WHERE id = ?", (row["id"],))
        deleted_count += 1

    db.commit()
    return {"deletedCount": deleted_count, "freedBytes": freed_bytes}
