"""
SoilSense AI — SQLite User & Login Tracking Database

Persists registered users (Email/Password and Google OAuth) and
maintains an audit trail of every login event.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "soilsense_auth.db"


def get_db_path() -> Path:
    env_path = os.getenv("AUTH_DB_PATH")
    if env_path:
        return Path(env_path)
    return DEFAULT_DB_PATH


@contextmanager
def get_connection():
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=10.0)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create users and login_events tables if they do not exist."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                uid TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL,
                photo_url TEXT,
                auth_provider TEXT NOT NULL,
                password_hash TEXT,
                created_at TEXT NOT NULL,
                last_login_at TEXT NOT NULL,
                login_count INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS login_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_uid TEXT NOT NULL,
                email TEXT NOT NULL,
                display_name TEXT NOT NULL,
                auth_provider TEXT NOT NULL,
                login_at TEXT NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                FOREIGN KEY (user_uid) REFERENCES users(uid)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_login_events_login_at ON login_events(login_at DESC)"
        )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_password(password: str, salt: Optional[str] = None) -> str:
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return f"{salt}${dk.hex()}"


def _verify_password(password: str, stored_hash: str) -> bool:
    if not stored_hash or "$" not in stored_hash:
        return False
    salt, expected_hex = stored_hash.split("$", 1)
    candidate = _hash_password(password, salt)
    return hmac.compare_digest(candidate, stored_hash)


def _default_avatar(email: str) -> str:
    return f"https://api.dicebear.com/7.x/bottts/svg?seed={email}"


def _row_to_user(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "uid": row["uid"],
        "email": row["email"],
        "displayName": row["display_name"],
        "photoURL": row["photo_url"] or _default_avatar(row["email"]),
        "authProvider": row["auth_provider"],
        "createdAt": row["created_at"],
        "lastLoginAt": row["last_login_at"],
        "loginCount": row["login_count"],
    }


def _record_login_event(
    conn: sqlite3.Connection,
    uid: str,
    email: str,
    display_name: str,
    auth_provider: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    conn.execute(
        """
        INSERT INTO login_events (user_uid, email, display_name, auth_provider, login_at, ip_address, user_agent)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (uid, email, display_name, auth_provider, _now_iso(), ip_address, user_agent),
    )


def register_email_user(
    email: str,
    password: str,
    display_name: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Dict[str, Any]:
    normalized_email = email.strip().lower()
    name = (display_name or "").strip() or normalized_email.split("@")[0]
    now = _now_iso()
    uid = f"user_{secrets.token_hex(8)}"
    pwd_hash = _hash_password(password)
    photo = _default_avatar(normalized_email)

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT uid FROM users WHERE email = ?", (normalized_email,)
        ).fetchone()
        if existing:
            raise ValueError("EMAIL_EXISTS")

        conn.execute(
            """
            INSERT INTO users (uid, email, display_name, photo_url, auth_provider, password_hash, created_at, last_login_at, login_count)
            VALUES (?, ?, ?, ?, 'email', ?, ?, ?, 1)
            """,
            (uid, normalized_email, name, photo, pwd_hash, now, now),
        )
        _record_login_event(conn, uid, normalized_email, name, "email", ip_address, user_agent)
        row = conn.execute("SELECT * FROM users WHERE uid = ?", (uid,)).fetchone()
        return _row_to_user(row)


def authenticate_email_user(
    email: str,
    password: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Dict[str, Any]:
    normalized_email = email.strip().lower()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?", (normalized_email,)
        ).fetchone()
        if not row:
            raise LookupError("USER_NOT_FOUND")
        if not row["password_hash"] or not _verify_password(password, row["password_hash"]):
            raise PermissionError("INVALID_PASSWORD")

        now = _now_iso()
        conn.execute(
            """
            UPDATE users
            SET last_login_at = ?, login_count = login_count + 1
            WHERE uid = ?
            """,
            (now, row["uid"]),
        )
        _record_login_event(
            conn, row["uid"], row["email"], row["display_name"], "email", ip_address, user_agent
        )
        updated = conn.execute("SELECT * FROM users WHERE uid = ?", (row["uid"],)).fetchone()
        return _row_to_user(updated)


def upsert_google_user(
    email: str,
    display_name: Optional[str] = None,
    photo_url: Optional[str] = None,
    uid: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Dict[str, Any]:
    normalized_email = email.strip().lower()
    name = (display_name or "").strip() or normalized_email.split("@")[0]
    now = _now_iso()

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM users WHERE email = ?", (normalized_email,)
        ).fetchone()

        if existing:
            resolved_uid = existing["uid"]
            resolved_name = name or existing["display_name"]
            resolved_photo = photo_url or existing["photo_url"] or _default_avatar(normalized_email)
            conn.execute(
                """
                UPDATE users
                SET display_name = ?,
                    photo_url = ?,
                    last_login_at = ?,
                    login_count = login_count + 1
                WHERE uid = ?
                """,
                (resolved_name, resolved_photo, now, resolved_uid),
            )
            _record_login_event(
                conn, resolved_uid, normalized_email, resolved_name, "google", ip_address, user_agent
            )
            updated = conn.execute("SELECT * FROM users WHERE uid = ?", (resolved_uid,)).fetchone()
            return _row_to_user(updated)

        resolved_uid = uid or f"google_{secrets.token_hex(8)}"
        resolved_photo = photo_url or _default_avatar(normalized_email)
        conn.execute(
            """
            INSERT INTO users (uid, email, display_name, photo_url, auth_provider, password_hash, created_at, last_login_at, login_count)
            VALUES (?, ?, ?, ?, 'google', NULL, ?, ?, 1)
            """,
            (resolved_uid, normalized_email, name, resolved_photo, now, now),
        )
        _record_login_event(
            conn, resolved_uid, normalized_email, name, "google", ip_address, user_agent
        )
        created = conn.execute("SELECT * FROM users WHERE uid = ?", (resolved_uid,)).fetchone()
        return _row_to_user(created)


def list_users() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM users ORDER BY last_login_at DESC"
        ).fetchall()
        return [_row_to_user(r) for r in rows]


def list_login_events(limit: int = 50) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, user_uid, email, display_name, auth_provider, login_at, ip_address, user_agent
            FROM login_events
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [
            {
                "id": r["id"],
                "uid": r["user_uid"],
                "email": r["email"],
                "displayName": r["display_name"],
                "authProvider": r["auth_provider"],
                "loginAt": r["login_at"],
                "ipAddress": r["ip_address"],
                "userAgent": r["user_agent"],
            }
            for r in rows
        ]
