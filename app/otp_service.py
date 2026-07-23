import hashlib
import secrets
from datetime import timedelta

from app.config import settings
from app.database import get_db_connection, pst_now, pst_str

OTP_PURPOSE_PASSWORD_RESET = "password_reset"
OTP_PURPOSE_REGISTRATION = "registration"


def _hash_otp(email: str, otp: str, purpose: str) -> str:
    payload = f"{purpose}:{email}:{otp}:{settings.jwt_secret_key}"
    return hashlib.sha256(payload.encode()).hexdigest()


def generate_otp() -> str:
    return f"{secrets.randbelow(900000) + 100000:06d}"


def store_otp(email: str, otp: str, purpose: str = OTP_PURPOSE_PASSWORD_RESET) -> None:
    conn = get_db_connection()
    otp_hash = _hash_otp(email, otp, purpose)
    expires_at = pst_str(pst_now() + timedelta(minutes=settings.otp_expiry_minutes))

    conn.execute(
        "DELETE FROM password_otps WHERE email = ? AND purpose = ?",
        (email, purpose),
    )
    conn.execute(
        "INSERT INTO password_otps (email, otp_hash, expires_at, created_at, purpose) VALUES (?, ?, ?, ?, ?)",
        (email, otp_hash, expires_at, pst_str(), purpose),
    )
    conn.commit()


def verify_otp(
    email: str,
    otp: str,
    purpose: str = OTP_PURPOSE_PASSWORD_RESET,
    *,
    consume: bool = True,
) -> bool:
    conn = get_db_connection()
    row = conn.execute(
        "SELECT otp_hash, expires_at FROM password_otps WHERE email = ? AND purpose = ?",
        (email, purpose),
    ).fetchone()

    if not row:
        return False

    if pst_str() > row["expires_at"]:
        conn.execute(
            "DELETE FROM password_otps WHERE email = ? AND purpose = ?",
            (email, purpose),
        )
        conn.commit()
        return False

    if _hash_otp(email, otp, purpose) != row["otp_hash"]:
        return False

    if consume:
        conn.execute(
            "DELETE FROM password_otps WHERE email = ? AND purpose = ?",
            (email, purpose),
        )
        conn.commit()
    return True


def can_request_otp(email: str, purpose: str = OTP_PURPOSE_PASSWORD_RESET) -> bool:
    conn = get_db_connection()
    row = conn.execute(
        """
        SELECT created_at FROM password_otps
        WHERE email = ? AND purpose = ?
        ORDER BY created_at DESC LIMIT 1
        """,
        (email, purpose),
    ).fetchone()
    if not row:
        return True

    from datetime import datetime

    created = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S")
    now = pst_now().replace(tzinfo=None)
    return now >= created + timedelta(seconds=60)


def store_password_reset_otp(user_id: str, email: str, otp: str) -> None:
    conn = get_db_connection()
    otp_hash = _hash_otp(email, otp, OTP_PURPOSE_PASSWORD_RESET)
    expires_at = pst_str(pst_now() + timedelta(minutes=5))  # 5 minutes expiration
    now_str = pst_str()

    # Deletes any existing OTPs for this user to ensure only one active OTP
    conn.execute("DELETE FROM password_reset_otps WHERE user_id = ?", (user_id,))
    conn.execute(
        """
        INSERT INTO password_reset_otps (user_id, email, otp_code, expires_at, verified, attempts, created_at, updated_at)
        VALUES (?, ?, ?, ?, 0, 0, ?, ?)
        """,
        (user_id, email, otp_hash, expires_at, now_str, now_str),
    )
    conn.commit()


def verify_password_reset_otp(email: str, otp: str) -> bool:
    conn = get_db_connection()
    now_str = pst_str()
    row = conn.execute(
        """
        SELECT id, otp_code, expires_at, verified, attempts FROM password_reset_otps
        WHERE email = ? AND verified = 0
        ORDER BY created_at DESC LIMIT 1
        """,
        (email,),
    ).fetchone()

    if not row:
        return False

    attempts = row["attempts"] + 1
    conn.execute(
        "UPDATE password_reset_otps SET attempts = ?, updated_at = ? WHERE id = ?",
        (attempts, now_str, row["id"]),
    )
    conn.commit()

    if attempts > 5:
        # Rejected due to too many attempts
        return False

    # Check expiration
    if now_str > row["expires_at"]:
        return False

    # Check OTP correctness
    expected_hash = _hash_otp(email, otp, OTP_PURPOSE_PASSWORD_RESET)
    if expected_hash != row["otp_code"]:
        return False

    # Mark as verified (verified = 1)
    conn.execute(
        "UPDATE password_reset_otps SET verified = 1, updated_at = ? WHERE id = ?",
        (now_str, row["id"]),
    )
    conn.commit()
    return True


def can_request_password_reset_otp(email: str) -> bool:
    conn = get_db_connection()
    row = conn.execute(
        """
        SELECT created_at FROM password_reset_otps
        WHERE email = ?
        ORDER BY created_at DESC LIMIT 1
        """,
        (email,),
    ).fetchone()
    if not row:
        return True

    from datetime import datetime
    created = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S")
    now = pst_now().replace(tzinfo=None)
    return now >= created + timedelta(seconds=60)

