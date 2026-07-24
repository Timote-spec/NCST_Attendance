"""Centralized password hashing and verification utilities.

All password operations in the backend should use these helpers to ensure
consistent bcrypt format across hashing, verification, and seeding.
"""

import bcrypt as _bcrypt


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt and return the hash string."""
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a bcrypt hash string.

    Returns False for empty/None hashes to avoid crashes on legacy rows.
    """
    if not password_hash:
        return False
    return _bcrypt.checkpw(password.encode(), password_hash.encode())
