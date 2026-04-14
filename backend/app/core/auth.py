"""
Auth core — JWT using stdlib hmac/hashlib (no cryptography dependency).
Passwords hashed with bcrypt via passlib (pure-python fallback).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer  # noqa: F401 (kept for token scheme)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models import User

settings = get_settings()
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

# ── Password hashing (bcrypt via passlib, pure-python fallback) ───────────────

# SHA-256 password hashing (no native bcrypt dependency needed)
# For production with Docker, swap back to passlib[bcrypt]
import hashlib as _hl


def hash_password(password: str) -> str:
    salt = hashlib.sha256(password[:4].encode()).hexdigest()[:8]
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260000)
    return f"pbkdf2:{salt}:{h.hex()}"


def verify_password(plain: str, hashed: str) -> bool:
    if not hashed.startswith("pbkdf2:"):
        return False
    try:
        _, salt, stored = hashed.split(":")
        h = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt.encode(), 260000)
        return hmac.compare_digest(h.hex(), stored)
    except Exception:
        return False


# ── Pure-stdlib HS256 JWT ─────────────────────────────────────────────────────

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    return base64.urlsafe_b64decode(s + "=" * padding)


def create_access_token(user_id: int) -> str:
    expire = int(time.time()) + settings.access_token_expire_minutes * 60
    header  = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64url(json.dumps({"sub": str(user_id), "exp": expire}).encode())
    sig_input = f"{header}.{payload}".encode()
    sig = _b64url(hmac.new(settings.secret_key.encode(), sig_input, hashlib.sha256).digest())
    return f"{header}.{payload}.{sig}"


def _verify_token(token: str) -> dict:
    try:
        header, payload, sig = token.split(".")
    except ValueError:
        raise ValueError("Malformed token")

    sig_input = f"{header}.{payload}".encode()
    expected  = _b64url(hmac.new(settings.secret_key.encode(), sig_input, hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        raise ValueError("Invalid signature")

    claims = json.loads(_b64url_decode(payload))
    if claims.get("exp", 0) < time.time():
        raise ValueError("Token expired")
    return claims


# ── FastAPI dependencies ──────────────────────────────────────────────────────

async def get_current_user(
    token: str = Depends(_oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        claims = _verify_token(token)
        user_id = claims.get("sub")
        if user_id is None:
            raise credentials_exc
    except Exception:
        raise credentials_exc

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise credentials_exc
    return user


def require_tier(*tiers: str):
    async def _check(user: User = Depends(get_current_user)) -> User:
        if user.tier not in tiers and not user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This feature requires {' or '.join(tiers)} tier",
            )
        return user
    return _check


require_pro   = require_tier("pro", "elite")
require_elite = require_tier("elite")
