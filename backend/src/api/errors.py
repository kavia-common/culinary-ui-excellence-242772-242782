"""Centralized error handling helpers for consistent API responses."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException, status


# PUBLIC_INTERFACE
def http_error(
    *,
    code: str,
    message: str,
    status_code: int = status.HTTP_400_BAD_REQUEST,
    details: Optional[dict[str, Any]] = None,
) -> HTTPException:
    """Create an HTTPException with a consistent {code,message,details} shape."""
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message, "details": details},
    )
