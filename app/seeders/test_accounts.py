"""Seed default test accounts for local development and demos.

Accounts are idempotent — running multiple times will not create duplicates.
Passwords are bcrypt-hashed before storage.
"""

from __future__ import annotations

import bcrypt as _bcrypt
import sqlite3

from app.database import get_db_connection, pst_str

TEST_ACCOUNTS = {
    "admin": {
        "kind": "ADMIN",
        "password": "admin123",
        "email": "admin@ncst.edu.ph",
        "first_name": "Test",
        "last_name": "Administrator",
    },
    "paullacuesta": {
        "kind": "ADMIN",
        "password": "NCST 2026",
        "email": "paullacuesta@gmail.com",
        "first_name": "Paul",
        "last_name": "Lacuesta",
    },
    "student": {
        "kind": "REGISTRANT",
        "password": "student123",
        "email": "student@ncst.edu",
        "first_name": "Test",
        "last_name": "Student",
        "role": "STUDENT",
        "department_section": "BSCS-3A",
        "course": "BSCS",
        "year_level": "3",
        "section": "A",
    },
    "staff": {
        "kind": "REGISTRANT",
        "password": "staff123",
        "email": "staff@ncst.edu",
        "first_name": "Test",
        "last_name": "Staff",
        "role": "STAFF",
        "department_section": "IT Department",
    },
    "faculty": {
        "kind": "REGISTRANT",
        "password": "faculty123",
        "email": "faculty@ncst.edu",
        "first_name": "Test",
        "last_name": "Faculty",
        "role": "FACULTY",
        "department_section": "College of Engineering",
        "course": "BSCS",
    },
}


def _hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


def _upsert_admin(conn: sqlite3.Connection, username: str, account: dict) -> None:
    password_hash = _hash_password(account["password"])
    existing = conn.execute(
        "SELECT admin_id FROM admins WHERE admin_id = ? OR email = ?",
        (username, account["email"]),
    ).fetchone()
    if existing:
        conn.execute(
            """
            UPDATE admins
               SET admin_id = ?, email = ?, password_hash = ?, first_name = ?, last_name = ?
             WHERE admin_id = ? OR email = ?
            """,
            (
                username,
                account["email"],
                password_hash,
                account["first_name"],
                account["last_name"],
                username,
                account["email"],
            ),
        )
    else:
        conn.execute(
            """
            INSERT INTO admins (admin_id, email, password_hash, first_name, last_name, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                username,
                account["email"],
                password_hash,
                account["first_name"],
                account["last_name"],
                pst_str(),
            ),
        )


def _upsert_registrant(conn: sqlite3.Connection, username: str, account: dict) -> None:
    password_hash = _hash_password(account["password"])
    existing = conn.execute(
        "SELECT user_id FROM registrants WHERE user_id = ? OR email = ?",
        (username, account["email"]),
    ).fetchone()
    if existing:
        conn.execute(
            """
            UPDATE registrants
               SET user_id = ?, email = ?, password_hash = ?, first_name = ?, last_name = ?,
                   role = ?, department_section = ?, course = ?, year_level = ?, section = ?,
                   status = 'ACTIVE'
             WHERE user_id = ? OR email = ?
            """,
            (
                username,
                account["email"],
                password_hash,
                account["first_name"],
                account["last_name"],
                account["role"],
                account["department_section"],
                account.get("course"),
                account.get("year_level"),
                account.get("section"),
                username,
                account["email"],
            ),
        )
    else:
        conn.execute(
            """
            INSERT INTO registrants (
                user_id, first_name, last_name, role, department_section,
                email, password_hash, course, year_level, section, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?)
            """,
            (
                username,
                account["first_name"],
                account["last_name"],
                account["role"],
                account["department_section"],
                account["email"],
                password_hash,
                account.get("course"),
                account.get("year_level"),
                account.get("section"),
                pst_str(),
            ),
        )


def seed_test_accounts(conn: sqlite3.Connection | None = None) -> None:
    """Create or refresh test accounts. Safe to call on every application startup."""
    conn = conn or get_db_connection()
    for username, account in TEST_ACCOUNTS.items():
        if account["kind"] == "ADMIN":
            _upsert_admin(conn, username, account)
        else:
            _upsert_registrant(conn, username, account)
    conn.commit()
    for username, account in TEST_ACCOUNTS.items():
        if account["kind"] != "ADMIN":
            try:
                from app.services.qr_service import ensure_qr_for_user
                ensure_qr_for_user(conn, username, force_regen=False)
            except Exception:
                pass


if __name__ == "__main__":
    from app.database import init_db

    init_db()
    seed_test_accounts()
    print("Test accounts seeded successfully.")
    print("  Admin:   username=admin   password=admin123")
    print("  Student: username=student password=student123")
    print("  Staff:   username=staff   password=staff123")
    print("  Faculty: username=faculty password=faculty123")
