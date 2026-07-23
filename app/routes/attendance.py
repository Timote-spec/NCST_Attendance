import datetime
import logging

import numpy as np
from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from app.config import settings
from app.database import get_db_connection, pst_now, pst_str
from app.schemas import AttendanceLogResponse, RfidAttendanceRequest
from app.services.face_service import face_service

logger = logging.getLogger("attendance")

router = APIRouter()

COOLDOWN_SECONDS = settings.scan_cooldown_seconds
MIN_INTERVAL_MINUTES = settings.min_attendance_interval_minutes


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def _check_cooldown(conn, user_id: str) -> bool:
    row = conn.execute(
        """SELECT logged_at FROM attendance_logs
           WHERE user_id = ? ORDER BY logged_at DESC LIMIT 1""",
        (user_id,),
    ).fetchone()
    if not row:
        return False
    try:
        last = datetime.datetime.strptime(str(row["logged_at"])[:19], "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return False
    now = pst_now().replace(tzinfo=None)
    elapsed = (now - last).total_seconds()
    return elapsed < COOLDOWN_SECONDS


def _parse_time(t: str) -> datetime.datetime:
    """Parse HH:MM:SS into a datetime.time for comparison."""
    parts = t.strip().split(":")
    return datetime.time(int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0)


def _process_attendance(conn, user_id: str, device_id: str, scan_method: str = "Face"):
    """Record attendance — always inserts a new row (no daily check-in/out logic)."""
    now = pst_now()
    today_date = now.strftime("%Y-%m-%d")
    now_time = now.strftime("%H:%M:%S")
    now_str = pst_str(now)

    cutoff = settings.late_cutoff_time
    status = "LATE" if now_time > cutoff else "PRESENT"
    cur = conn.execute(
        """INSERT INTO attendance_logs (user_id, device_id, logged_at, time_in, time_out, attendance_status, date, scan_method)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, device_id, now_str, now_time, None, status, today_date, scan_method),
    )
    conn.commit()
    record = _fetch_attendance_record(conn, cur.lastrowid)
    return _build_attendance_response(record, action="in")


def _fetch_attendance_record(conn, log_id: int):
    record = conn.execute(
        """SELECT a.user_id,
                  r.first_name || ' ' || r.last_name AS user_name,
                  a.logged_at, a.device_id, a.time_in, a.time_out, a.attendance_status, a.date, a.scan_method,
                  r.section, r.course, r.year_level, r.department_section, r.photo_path
             FROM attendance_logs a
             JOIN registrants r ON r.user_id = a.user_id
            WHERE a.log_id = ?""",
        (log_id,),
    ).fetchone()
    return record


def _build_attendance_response(record, action="in") -> AttendanceLogResponse:
    photo_path = None
    try:
        photo_path = record["photo_path"]
    except (IndexError, KeyError):
        pass
    photo_url = f"/api/v1/images/{record['user_id']}" if photo_path else None

    def _get(key, default=None):
        try:
            return record[key]
        except (IndexError, KeyError):
            return default

    return AttendanceLogResponse(
        user_id=record["user_id"],
        user_name=record["user_name"],
        logged_at=record["logged_at"],
        device_id=record["device_id"],
        time_in=record["time_in"],
        time_out=record["time_out"],
        attendance_status=record["attendance_status"],
        date=record["date"],
        photo_url=photo_url,
        section=_get("section"),
        course=_get("course"),
        year_level=_get("year_level"),
        department_section=_get("department_section"),
        scan_action=action,
        scan_method=_get("scan_method"),
    )


@router.post("/verify", response_model=AttendanceLogResponse)
async def verify_attendance(
    device_id: str = Form(...),
    image: UploadFile = File(...),
):
    logger.info("[FACE] verify_attendance called — device=%s", device_id)
    image_bytes = await image.read()
    logger.info("[FACE] Image received: %d bytes", len(image_bytes))
    try:
        query_emb = await face_service.extract_embedding(image_bytes)
    except ValueError as e:
        logger.warning("[FACE] Embedding extraction failed: %s", e)
        raise HTTPException(status_code=400, detail=str(e))

    query_vec = np.array(query_emb, dtype=np.float32)

    conn = get_db_connection()
    rows = conn.execute(
        """SELECT user_id, first_name, last_name, face_embedding
             FROM registrants
            WHERE status = 'ACTIVE' AND face_embedding IS NOT NULL"""
    ).fetchall()

    if not rows:
        logger.warning("[FACE] No active registrants with face embeddings")
        raise HTTPException(status_code=404, detail="No active registrants found")

    best_match_id = None
    best_sim = -1.0

    for row in rows:
        stored_vec = np.frombuffer(row["face_embedding"], dtype=np.float32)
        sim = _cosine_similarity(query_vec, stored_vec)
        if sim > best_sim:
            best_sim = sim
            best_match_id = row["user_id"]

    logger.info("[FACE] Best match: user=%s similarity=%.4f (threshold=%.4f)", best_match_id, best_sim, settings.matching_threshold)

    if best_match_id is None or best_sim < settings.matching_threshold:
        logger.warning("[FACE] No match above threshold — highest was %.4f", best_sim)
        raise HTTPException(
            status_code=401,
            detail=f"Match not found (highest similarity: {best_sim:.2f})",
        )

    if _check_cooldown(conn, best_match_id):
        logger.info("[FACE] Cooldown active for user=%s", best_match_id)
        raise HTTPException(
            status_code=429,
            detail=f"Already recorded recently. Please wait {COOLDOWN_SECONDS}s between scans.",
        )

    logger.info("[FACE] Attendance recorded for user=%s", best_match_id)
    return _process_attendance(conn, best_match_id, device_id, "Face")


@router.post("/verify/qr", response_model=AttendanceLogResponse)
def verify_qr_attendance(
    qr_token: str = Form(...),
    device_id: str = Form("qr-scanner-01"),
):
    # Frontend sends Form field `qr_token`, but QR now encodes an encrypted payload.
    qr_value = (qr_token or "").strip()
    logger.info("[QR] verify_qr_attendance called — payload_len=%s, device=%s", len(qr_value), device_id)

    conn = get_db_connection()
    from app.services.qr_service import decrypt_payload

    try:
        decoded = decrypt_payload(qr_value)
    except Exception:
        logger.warning("[QR] Payload decryption failed")
        raise HTTPException(status_code=401, detail="Invalid or expired QR code")

    row = conn.execute(
        """SELECT user_id, first_name, last_name, role, status, section, course, year_level, department_section, photo_path
             FROM registrants
            WHERE user_id = ? AND qr_token = ? AND status = 'ACTIVE'""",
        (decoded.user_id, decoded.qr_token),
    ).fetchone()


    if not row:
        raise HTTPException(status_code=401, detail="Invalid or inactive QR code")

    user_id = row["user_id"]

    logger.info("[QR] Matched user=%s %s %s", user_id, row["first_name"], row["last_name"])

    if _check_cooldown(conn, user_id):
        logger.info("[QR] Cooldown active for user=%s", user_id)
        raise HTTPException(
            status_code=429,
            detail=f"Already recorded recently. Please wait {COOLDOWN_SECONDS}s between scans.",
        )

    logger.info("[QR] Attendance recorded for user=%s", user_id)
    return _process_attendance(conn, user_id, device_id, "QR")


@router.post("/verify/rfid", response_model=AttendanceLogResponse)
def verify_rfid_attendance(
    rfid_uid: str = Form(...),
    device_id: str = Form("rfid-scanner-01"),
):
    rfid_value = (rfid_uid or "").strip()
    logger.info("[RFID] verify_rfid_attendance called — uid=%s, device=%s", rfid_value, device_id)

    if not rfid_value:
        raise HTTPException(status_code=400, detail="RFID UID is required")

    conn = get_db_connection()
    row = conn.execute(
        """SELECT user_id, first_name, last_name, role, status, section, course, year_level, department_section, photo_path
             FROM registrants
            WHERE rfid_uid = ? AND status = 'ACTIVE'""",
        (rfid_value,),
    ).fetchone()

    if not row:
        raise HTTPException(status_code=401, detail="RFID card not recognized or user is inactive")

    user_id = row["user_id"]
    logger.info("[RFID] Matched user=%s %s %s", user_id, row["first_name"], row["last_name"])

    if _check_cooldown(conn, user_id):
        logger.info("[RFID] Cooldown active for user=%s", user_id)
        raise HTTPException(
            status_code=429,
            detail=f"Already recorded recently. Please wait {COOLDOWN_SECONDS}s between scans.",
        )

    logger.info("[RFID] Attendance recorded for user=%s", user_id)
    return _process_attendance(conn, user_id, device_id, "RFID")


@router.post("/attendance/rfid", response_model=AttendanceLogResponse)
def rfid_attendance_json(body: RfidAttendanceRequest, device_id: str = "rfid-scanner-01"):
    rfid_value = (body.rfid_uid or "").strip()
    logger.info("[RFID-JSON] attendance/rfid called — uid=%s, device=%s", rfid_value, device_id)

    if not rfid_value:
        raise HTTPException(status_code=400, detail="RFID UID is required")

    conn = get_db_connection()
    row = conn.execute(
        """SELECT user_id, first_name, last_name, role, status, section, course, year_level, department_section, photo_path
             FROM registrants
            WHERE rfid_uid = ? AND status = 'ACTIVE'""",
        (rfid_value,),
    ).fetchone()

    if not row:
        raise HTTPException(status_code=401, detail="RFID card not recognized or user is inactive")

    user_id = row["user_id"]
    logger.info("[RFID-JSON] Matched user=%s %s %s", user_id, row["first_name"], row["last_name"])

    if _check_cooldown(conn, user_id):
        logger.info("[RFID-JSON] Cooldown active for user=%s", user_id)
        raise HTTPException(
            status_code=429,
            detail=f"Already recorded recently. Please wait {COOLDOWN_SECONDS}s between scans.",
        )

    logger.info("[RFID-JSON] Attendance recorded for user=%s", user_id)
    return _process_attendance(conn, user_id, device_id, "RFID")


# Alias: some clients (including the existing /rfid-scanner.html) post to
# POST /api/v1/attendance/rfid (without the extra `attendance/` segment).
# Keep backward compatibility without removing existing endpoints.
@router.post("/rfid", response_model=AttendanceLogResponse)
def rfid_attendance_json_alias(body: RfidAttendanceRequest, device_id: str = "rfid-scanner-01"):
    return rfid_attendance_json(body=body, device_id=device_id)

