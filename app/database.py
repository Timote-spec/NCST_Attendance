import sqlite3
import threading
from datetime import datetime
from pathlib import Path

import bcrypt as _bcrypt

from app.config import settings
from app.utils import get_pst_now

DB_PATH = Path(settings.database_path)


def pst_now() -> datetime:
    return get_pst_now()


def pst_str(dt: datetime | None = None) -> str:
    return (dt if dt else pst_now()).strftime("%Y-%m-%d %H:%M:%S")


_local = threading.local()


def get_db_connection() -> sqlite3.Connection:
    conn = getattr(_local, "connection", None)
    if conn is None:
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        _local.connection = conn
    return conn


def _has_column(conn, table, column):
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r["name"] == column for r in rows)


def _migrate_students(conn):
    """Add missing columns to registrants for extended profile and login."""
    if not _has_column(conn, "registrants", "email"):
        conn.execute("ALTER TABLE registrants ADD COLUMN email TEXT")
    if not _has_column(conn, "registrants", "photo_path"):
        conn.execute("ALTER TABLE registrants ADD COLUMN photo_path TEXT")
    if not _has_column(conn, "registrants", "qr_token"):
        conn.execute("ALTER TABLE registrants ADD COLUMN qr_token TEXT")
    if not _has_column(conn, "registrants", "qr_payload_enc"):
        conn.execute("ALTER TABLE registrants ADD COLUMN qr_payload_enc TEXT")
    if not _has_column(conn, "registrants", "qr_image_path"):
        conn.execute("ALTER TABLE registrants ADD COLUMN qr_image_path TEXT")

    if not _has_column(conn, "registrants", "password_hash"):
        conn.execute("ALTER TABLE registrants ADD COLUMN password_hash TEXT")
    if not _has_column(conn, "registrants", "course"):
        conn.execute("ALTER TABLE registrants ADD COLUMN course TEXT")
    if not _has_column(conn, "registrants", "year_level"):
        conn.execute("ALTER TABLE registrants ADD COLUMN year_level TEXT")
    if not _has_column(conn, "registrants", "section"):
        conn.execute("ALTER TABLE registrants ADD COLUMN section TEXT")
    if not _has_column(conn, "registrants", "contact_number"):
        conn.execute("ALTER TABLE registrants ADD COLUMN contact_number TEXT")
    if not _has_column(conn, "registrants", "address"):
        conn.execute("ALTER TABLE registrants ADD COLUMN address TEXT")
    if not _has_column(conn, "registrants", "emergency_contact"):
        conn.execute("ALTER TABLE registrants ADD COLUMN emergency_contact TEXT")
    conn.commit()
    # Backfill email for registrants missing it (use user_id@ncst.local placeholder)
    conn.execute(
        "UPDATE registrants SET email = user_id || '@ncst.local' WHERE email IS NULL OR email = ''"
    )
    conn.commit()


def _migrate_admins(conn):
    """Add status column to admins table."""
    if not _has_column(conn, "admins", "status"):
        conn.execute("ALTER TABLE admins ADD COLUMN status TEXT NOT NULL DEFAULT 'ACTIVE'")
        conn.commit()
    conn.execute(
        "UPDATE admins SET status = 'ACTIVE' WHERE status IS NULL OR status = ''"
    )
    conn.commit()


def _migrate_rfid(conn):
    """Add rfid_uid column to registrants for RFID-based attendance."""
    if not _has_column(conn, "registrants", "rfid_uid"):
        conn.execute("ALTER TABLE registrants ADD COLUMN rfid_uid TEXT")
        conn.commit()


def _migrate_attendance_logs(conn):
    """Add time_in/time_out tracking columns to attendance_logs."""
    if not _has_column(conn, "attendance_logs", "time_in"):
        conn.execute("ALTER TABLE attendance_logs ADD COLUMN time_in TEXT")
    if not _has_column(conn, "attendance_logs", "time_out"):
        conn.execute("ALTER TABLE attendance_logs ADD COLUMN time_out TEXT")
    if not _has_column(conn, "attendance_logs", "attendance_status"):
        conn.execute("ALTER TABLE attendance_logs ADD COLUMN attendance_status TEXT DEFAULT 'PRESENT'")
    if not _has_column(conn, "attendance_logs", "date"):
        conn.execute("ALTER TABLE attendance_logs ADD COLUMN date TEXT")
    if not _has_column(conn, "attendance_logs", "scan_method"):
        conn.execute("ALTER TABLE attendance_logs ADD COLUMN scan_method TEXT DEFAULT 'Face'")
    conn.commit()
    # Backfill date from logged_at for existing rows
    conn.execute(
        """
        UPDATE attendance_logs
           SET date = substr(logged_at, 1, 10)
         WHERE date IS NULL
        """
    )
    conn.commit()


def init_db():
    conn = get_db_connection()

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS admins (
            admin_id        TEXT PRIMARY KEY,
            email           TEXT UNIQUE NOT NULL,
            password_hash   TEXT NOT NULL,
            first_name      TEXT NOT NULL,
            last_name       TEXT NOT NULL,
            created_at      TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS registrants (
            user_id             TEXT PRIMARY KEY,
            first_name          TEXT NOT NULL,
            last_name           TEXT NOT NULL,
            role                TEXT NOT NULL CHECK(role IN ('STUDENT','STAFF','FACULTY')),
            department_section  TEXT NOT NULL,
            face_embedding      BLOB,
            status              TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','ARCHIVED')),
            created_at          TIMESTAMP,
            qr_token            TEXT,
            qr_payload_enc     TEXT,
            qr_image_path      TEXT
        );


        CREATE TABLE IF NOT EXISTS attendance_logs (
            log_id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id           TEXT NOT NULL REFERENCES registrants(user_id),
            logged_at         TIMESTAMP,
            device_id         TEXT NOT NULL,
            time_in           TEXT,
            time_out          TEXT,
            attendance_status TEXT NOT NULL DEFAULT 'PRESENT',
            date              TEXT
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            log_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_email TEXT,
            action      TEXT NOT NULL,
            details     TEXT,
            logged_at   TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS password_otps (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            email       TEXT NOT NULL,
            otp_hash    TEXT NOT NULL,
            expires_at  TIMESTAMP NOT NULL,
            created_at  TIMESTAMP NOT NULL,
            purpose     TEXT NOT NULL DEFAULT 'password_reset'
        );

        CREATE TABLE IF NOT EXISTS password_reset_otps (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     TEXT NOT NULL,
            email       TEXT NOT NULL,
            otp_code    TEXT NOT NULL,
            expires_at  TIMESTAMP NOT NULL,
            verified    INTEGER NOT NULL DEFAULT 0,
            attempts    INTEGER NOT NULL DEFAULT 0,
            created_at  TIMESTAMP NOT NULL,
            updated_at  TIMESTAMP NOT NULL
        );

        CREATE TABLE IF NOT EXISTS announcements (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT NOT NULL,
            content     TEXT NOT NULL,
            target_role TEXT NOT NULL DEFAULT 'ALL' CHECK(target_role IN ('ALL','STUDENT','STAFF','FACULTY')),
            created_by  TEXT NOT NULL,
            created_at  TIMESTAMP,
            is_pinned   INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       TEXT NOT NULL,
            title         TEXT NOT NULL,
            message       TEXT NOT NULL,
            notification_type TEXT NOT NULL DEFAULT 'INFO' CHECK(notification_type IN ('INFO','ATTENDANCE','APPROVAL','SYSTEM')),
            is_read       INTEGER NOT NULL DEFAULT 0,
            created_at    TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS profile_update_requests (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       TEXT NOT NULL,
            field_name    TEXT NOT NULL,
            old_value     TEXT,
            new_value     TEXT NOT NULL,
            status        TEXT NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING','APPROVED','REJECTED')),
            requested_at  TIMESTAMP,
            reviewed_at   TIMESTAMP,
            reviewed_by   TEXT
        );

        CREATE TABLE IF NOT EXISTS approval_requests (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       TEXT NOT NULL,
            request_type  TEXT NOT NULL CHECK(request_type IN ('PROFILE_UPDATE','FACE_REREGISTER','ACCOUNT_REQUEST','PASSWORD_RESET')),
            details       TEXT,
            status        TEXT NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING','APPROVED','REJECTED')),
            requested_at  TIMESTAMP,
            reviewed_at   TIMESTAMP,
            reviewed_by   TEXT
        );

        CREATE TABLE IF NOT EXISTS face_registrations (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       TEXT NOT NULL,
            embedding     BLOB,
            captured_at   TIMESTAMP,
            status        TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','RE_REGISTRATION_PENDING','EXPIRED'))
        );
    """)

    conn.commit()
    _migrate_students(conn)
    _migrate_admins(conn)
    _migrate_attendance_logs(conn)
    _migrate_rfid(conn)
    _create_indexes(conn)
    _ensure_main_admin(conn)
    _ensure_qr_tokens(conn)
    from app.seeders.test_accounts import seed_test_accounts

    seed_test_accounts(conn)


def _create_indexes(conn: sqlite3.Connection):
    """Add performance/lookup indexes (idempotent)."""
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_registrants_email ON registrants(email)",
        "CREATE INDEX IF NOT EXISTS idx_registrants_role_status ON registrants(role, status)",
        "CREATE INDEX IF NOT EXISTS idx_registrants_face ON registrants(status, face_embedding)",
        "CREATE INDEX IF NOT EXISTS idx_attendance_user ON attendance_logs(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance_logs(date)",
        "CREATE INDEX IF NOT EXISTS idx_attendance_user_date ON attendance_logs(user_id, date)",
        "CREATE INDEX IF NOT EXISTS idx_attendance_logged ON attendance_logs(logged_at)",
        "CREATE INDEX IF NOT EXISTS idx_notifications_user_read ON notifications(user_id, is_read)",
        "CREATE INDEX IF NOT EXISTS idx_approvals_status ON approval_requests(status)",
        "CREATE INDEX IF NOT EXISTS idx_profile_requests_user ON profile_update_requests(user_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_audit_logged ON audit_logs(logged_at)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_registrants_qr ON registrants(qr_token) WHERE qr_token IS NOT NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_registrants_rfid ON registrants(rfid_uid) WHERE rfid_uid IS NOT NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_registrants_email_unique ON registrants(email) WHERE email IS NOT NULL",
        "CREATE INDEX IF NOT EXISTS idx_password_reset_otps_email ON password_reset_otps(email)",
        "CREATE INDEX IF NOT EXISTS idx_password_reset_otps_user ON password_reset_otps(user_id)",
    ]
    for sql in indexes:
        conn.execute(sql)
    conn.commit()


def _ensure_main_admin(conn: sqlite3.Connection):
    main_email = settings.main_admin_email.strip().lower()
    new_hash = _bcrypt.hashpw(
        "NCST 2026".encode(), _bcrypt.gensalt()
    ).decode()

    by_id = conn.execute(
        "SELECT admin_id, email, password_hash FROM admins WHERE admin_id = ?",
        ("admin",),
    ).fetchone()
    by_email = conn.execute(
        "SELECT admin_id, email, password_hash FROM admins WHERE email = ?",
        (main_email,),
    ).fetchone()

    if by_email:
        needs_password_update = _bcrypt.checkpw(
            b"admin123", by_email["password_hash"].encode()
        )
        password_hash = new_hash if needs_password_update else by_email["password_hash"]
        if by_email["admin_id"] != "admin" and by_id:
            conn.execute("DELETE FROM admins WHERE admin_id = ?", ("admin",))
        if by_email["admin_id"] != "admin" or needs_password_update:
            conn.execute(
                """
                UPDATE admins
                SET admin_id = ?, password_hash = ?, first_name = ?, last_name = ?
                WHERE email = ?
                """,
                ("admin", password_hash, "Paul", "Lacuesta", main_email),
            )
            conn.commit()
        return

    if by_id:
        needs_password_update = _bcrypt.checkpw(
            b"admin123", by_id["password_hash"].encode()
        )
        password_hash = new_hash if needs_password_update else by_id["password_hash"]
        conn.execute(
            """
            UPDATE admins
            SET email = ?, password_hash = ?, first_name = ?, last_name = ?
            WHERE admin_id = ?
            """,
            (main_email, password_hash, "Paul", "Lacuesta", "admin"),
        )
        conn.commit()
        return

    conn.execute(
        """
        INSERT INTO admins (admin_id, email, password_hash, first_name, last_name, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("admin", main_email, new_hash, "Paul", "Lacuesta", pst_str()),
    )
    conn.commit()


def _ensure_qr_tokens(conn):
    """Backfill QR token, encrypted payload, and stored PNG.

    This is idempotent and safe to run at startup.
    """
    from app.services.qr_service import ensure_qr_for_user

    rows = conn.execute(
        """SELECT user_id
             FROM registrants
            WHERE qr_token IS NULL OR qr_payload_enc IS NULL OR qr_image_path IS NULL"""
    ).fetchall()

    if not rows:
        return

    for row in rows:
        try:
            ensure_qr_for_user(conn, row["user_id"], force_regen=False)
        except Exception:
            pass

    conn.commit()




def log_system_action(admin_email: str | None, action: str, details: str | None = None):
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO audit_logs (admin_email, action, details, logged_at) VALUES (?, ?, ?, ?)",
        (admin_email, action, details, pst_str()),
    )
    conn.commit()


def get_admin_email(admin_id: str) -> str | None:
    conn = get_db_connection()
    row = conn.execute("SELECT email FROM admins WHERE admin_id = ?", (admin_id,)).fetchone()
    return row["email"] if row else None


def create_notification(
    user_id: str,
    title: str,
    message: str,
    notification_type: str = "INFO",
) -> None:
    """Create an in-app notification for a registrant (student/staff/faculty)."""
    conn = get_db_connection()
    conn.execute(
        """INSERT INTO notifications (user_id, title, message, notification_type, is_read, created_at)
           VALUES (?, ?, ?, ?, 0, ?)""",
        (user_id, title, message, notification_type, pst_str()),
    )
    conn.commit()


def get_user_role(user_id: str) -> str | None:
    conn = get_db_connection()
    row = conn.execute("SELECT role FROM registrants WHERE user_id = ?", (user_id,)).fetchone()
    return row["role"] if row else None


def find_user_by_email(email: str) -> dict | None:
    """Return a normalized account record for any role by email or username.

    Accepts admin email, admin_id, registrant email, or user_id (login field
    is labeled "Email / User ID" in the UI).

    Returns {'kind': 'ADMIN'|'REGISTRANT', 'id', 'email', 'password_hash', ...}
    """
    conn = get_db_connection()
    login = email.strip().lower()

    admin = conn.execute(
        "SELECT admin_id AS id, email, password_hash, first_name, last_name, COALESCE(status, 'ACTIVE') AS status FROM admins WHERE LOWER(email) = ?",
        (login,),
    ).fetchone()
    if not admin:
        admin = conn.execute(
            "SELECT admin_id AS id, email, password_hash, first_name, last_name, COALESCE(status, 'ACTIVE') AS status FROM admins WHERE LOWER(admin_id) = ?",
            (login,),
        ).fetchone()
    if admin:
        return {
            "kind": "ADMIN",
            "id": admin["id"],
            "email": admin["email"],
            "password_hash": admin["password_hash"],
            "first_name": admin["first_name"],
            "last_name": admin["last_name"],
            "status": admin["status"],
        }
    reg = conn.execute(
        """SELECT user_id AS id, email, password_hash, first_name, last_name, role, status
             FROM registrants WHERE LOWER(email) = ? AND password_hash IS NOT NULL""",
        (login,),
    ).fetchone()
    if not reg:
        reg = conn.execute(
            """SELECT user_id AS id, email, password_hash, first_name, last_name, role, status
                 FROM registrants WHERE LOWER(user_id) = ? AND password_hash IS NOT NULL""",
            (login,),
        ).fetchone()
    if reg:
        return {
            "kind": "REGISTRANT",
            "id": reg["id"],
            "email": reg["email"],
            "password_hash": reg["password_hash"],
            "first_name": reg["first_name"],
            "last_name": reg["last_name"],
            "role": reg["role"],
            "status": reg["status"],
        }
    return None
