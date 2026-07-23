import csv
import io
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from app.database import get_db_connection
from app.routes.auth import get_current_admin, get_current_user

router = APIRouter()


def _require_admin_or_staff(_user: dict = Depends(get_current_user)):
    if _user["role"] not in ("ADMIN", "STAFF", "FACULTY"):
        raise HTTPException(status_code=403, detail="Access denied")
    return _user


def _get_logs_query(date_from=None, date_to=None, search=None, role=None):
    conn = get_db_connection()
    sql = """SELECT a.log_id, a.user_id, r.first_name || ' ' || r.last_name AS user_name, r.role, r.department_section, a.logged_at, a.device_id, a.time_in, a.time_out, a.attendance_status, a.date
               FROM attendance_logs a
               JOIN registrants r ON r.user_id = a.user_id
              WHERE 1=1"""
    params = []
    if date_from:
        sql += " AND a.date >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND a.date <= ?"
        params.append(date_to)
    if search:
        sql += " AND (r.first_name LIKE ? OR r.last_name LIKE ? OR r.user_id LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like, like])
    if role:
        sql += " AND r.role = ?"
        params.append(role)
    return sql, params, conn


@router.get("/reports/export")
def export_report(
    report_type: str = Query("daily"),
    date: str = Query(None),
    date_from: str = Query(None),
    date_to: str = Query(None),
    search: str = Query(None),
    role: str = Query(None),
    format: str = Query("csv"),
    _admin: str = Depends(_require_admin_or_staff),
):
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    if report_type == "daily":
        date_from = target_date
        date_to = target_date
    elif report_type == "weekly":
        dt = datetime.strptime(target_date, "%Y-%m-%d")
        start = dt - timedelta(days=dt.weekday())
        date_from = start.strftime("%Y-%m-%d")
        date_to = target_date
    elif report_type == "monthly":
        date_from = target_date[:7] + "-01"
        date_to = target_date

    sql, params, conn = _get_logs_query(date_from, date_to, search, role)
    rows = conn.execute(sql + " ORDER BY a.date DESC, a.logged_at DESC", params).fetchall()

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Log ID", "Name", "Role", "Department", "Date", "Time In", "Time Out", "Status", "Logged At", "Device"])
        for r in rows:
            writer.writerow([
                r["log_id"], r["user_name"], r["role"], r["department_section"],
                r["date"], r["time_in"], r["time_out"], r["attendance_status"], r["logged_at"], r["device_id"]
            ])
        return Response(content=output.getvalue(), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=attendance_{report_type}_{target_date}.csv"})
    else:
        return {"total": len(rows), "items": [dict(r) for r in rows]}
