from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,32}$")
bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return salt.hex() + ":" + digest.hex()


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split(":", 1)
    except ValueError:
        return False
    check = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 200_000)
    return hmac.compare_digest(check.hex(), digest_hex)


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def validate_username(username: str) -> str:
    name = username.strip()
    if not USERNAME_RE.fullmatch(name):
        raise HTTPException(status_code=400, detail="Login: 3–32 znaki, litery, cyfry, _")
    return name


def validate_password(password: str) -> str:
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Hasło min. 6 znaków")
    return password


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Zaloguj się")
    user = db.query(User).filter(User.session_token == creds.credentials).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Zaloguj się")
    return user
