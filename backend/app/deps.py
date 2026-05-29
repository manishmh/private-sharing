"""Shared FastAPI dependencies: admin auth."""
from fastapi import Header, HTTPException, status

from app.config import settings


def require_admin(x_admin_password: str = Header(default="")) -> None:
    """Gate admin endpoints behind the single shared password.

    PRODUCTION: replace with real authentication (sessions/JWT + hashed users).
    """
    if x_admin_password != settings.admin_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin password",
        )
