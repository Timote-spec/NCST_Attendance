from fastapi import APIRouter, Depends

from app.database import get_db_connection, pst_now
from app.routes.auth import get_current_user

router = APIRouter()


@router.get("/dashboard/live")
def live_dashboard_stats(_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    now = pst_now()
    today = now.strftime("%Y-%m-%d")

    total = conn.execute("SELECT COUNT(*) FROM registrants WHERE status = 'ACTIVE'").fetchone()[0]

    row = conn.execute(
        """SELECT COUNT(*) AS total_att,
                  SUM(CASE WHEN attendance_status = 'PRESENT' THEN 1 ELSE 0 END) AS present,
                  SUM(CASE WHEN attendance_status = 'LATE' THEN 1 ELSE 0 END) AS late
             FROM attendance_logs WHERE date = ?""",
        (today,),
    ).fetchone()
    total_att = row["total_att"] or 0
    present = row["present"] or 0
    late = row["late"] or 0

    attended_today = conn.execute(
        "SELECT COUNT(DISTINCT user_id) FROM attendance_logs WHERE date = ?", (today,)
    ).fetchone()[0]

    absent = max(0, total - attended_today)

    return {
        "total_students": total,
        "present_today": present,
        "absent_today": absent,
        "late_today": late,
        "total_attendance_today": total_att,
        "unique_attendees": attended_today,
        "timestamp": now.strftime("%H:%M:%S"),
    }
