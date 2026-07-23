import json

from fastapi import APIRouter, Depends, HTTPException, Query

from app.database import (
    create_notification,
    get_db_connection,
    log_system_action,
    pst_str,
)
from app.routes.auth import get_current_admin
from app.schemas import ApprovalDecision, ApprovalRequestResponse, GenericResponse

router = APIRouter()


@router.get("/approvals", response_model=list[ApprovalRequestResponse])
def list_approvals(_admin: str = Depends(get_current_admin)):
    conn = get_db_connection()
    rows = conn.execute(
        """SELECT id, user_id, request_type, details, status, requested_at, reviewed_at, reviewed_by
                FROM approval_requests
            ORDER BY requested_at DESC"""
    ).fetchall()
    return [
        ApprovalRequestResponse(
            id=r["id"],
            user_id=r["user_id"],
            request_type=r["request_type"],
            details=r["details"],
            status=r["status"],
            requested_at=r["requested_at"],
            reviewed_at=r["reviewed_at"],
            reviewed_by=r["reviewed_by"],
        )
        for r in rows
    ]


@router.post("/approvals/{approval_id}/decide", response_model=GenericResponse)
def decide_approval(approval_id: int, body: ApprovalDecision, _admin: str = Depends(get_current_admin)):
    if body.decision not in ("APPROVED", "REJECTED"):
        raise HTTPException(status_code=400, detail="Decision must be APPROVED or REJECTED")
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM approval_requests WHERE id = ?", (approval_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Approval not found")
    if row["status"] != "PENDING":
        raise HTTPException(status_code=400, detail="Already reviewed")

    now = pst_str()
    conn.execute(
        """UPDATE approval_requests
              SET status = ?, reviewed_at = ?, reviewed_by = ?
            WHERE id = ?""",
        (body.decision, now, _admin, approval_id),
    )

    user_id = row["user_id"]
    request_type = row["request_type"]
    details = row["details"]

    if body.decision == "APPROVED":
        if request_type == "PROFILE_UPDATE":
            _apply_profile_changes(conn, user_id, details)
            create_notification(user_id, "Profile update approved", "Your requested profile changes have been applied.", "APPROVAL")
        elif request_type == "FACE_REREGISTER":
            create_notification(user_id, "Face re-registration approved", "You may now upload a new face image from your profile.", "APPROVAL")
        elif request_type == "ACCOUNT_REQUEST":
            create_notification(user_id, "Account request approved", "Your account request has been approved by an administrator.", "APPROVAL")
        elif request_type == "PASSWORD_RESET":
            create_notification(user_id, "Password reset approved", "Your password reset request has been approved.", "APPROVAL")
    else:
        if request_type == "PROFILE_UPDATE":
            create_notification(user_id, "Profile update rejected", "Your requested profile changes were not approved.", "APPROVAL")

    conn.commit()
    log_system_action(_admin, "APPROVAL_DECISION", f"{body.decision} approval {approval_id} for user {user_id}: {body.notes or ''}")
    return GenericResponse(status="ok", message=f"Request {body.decision.lower()} successfully")


def _apply_profile_changes(conn, user_id: str, details: str | None):
    """Apply approved profile-change fields to the registrants table."""
    if not details:
        return
    try:
        payload = json.loads(details)
        changes = payload.get("changes", {})
    except (json.JSONDecodeError, AttributeError):
        return

    allowed = {"first_name", "last_name", "email", "contact_number", "address", "emergency_contact", "course", "year_level", "section"}
    sets = {k: v for k, v in changes.items() if k in allowed}
    if not sets:
        return

    set_clause = ", ".join(f"{k} = ?" for k in sets)
    params = list(sets.values()) + [user_id]
    conn.execute(f"UPDATE registrants SET {set_clause} WHERE user_id = ?", params)

    # Mark the matching pending profile_update_requests as approved.
    for field in sets:
        conn.execute(
            """UPDATE profile_update_requests
                  SET status = 'APPROVED', reviewed_at = ?, reviewed_by = ?
                WHERE user_id = ? AND field_name = ? AND status = 'PENDING'""",
            (pst_str(), "system", user_id, field),
        )
