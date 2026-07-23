from fastapi import APIRouter, Depends

from app.database import get_db_connection
from app.routes.auth import get_current_user

router = APIRouter()


@router.get("/notifications")
def list_notifications(_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    rows = conn.execute(
        """SELECT id, user_id, title, message, notification_type, is_read, created_at
               FROM notifications
              WHERE user_id = ?
           ORDER BY created_at DESC""",
        (_user["user_id"],),
    ).fetchall()
    return [dict(r) for r in rows]


@router.post("/notifications/{notification_id}/read")
def mark_read(notification_id: int, _user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    conn.execute("UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?", (notification_id, _user["user_id"]))
    conn.commit()
    return {"status": "ok"}


@router.post("/notifications/mark-all-read")
def mark_all_read(_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    conn.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (_user["user_id"],))
    conn.commit()
    return {"status": "ok"}
