"""
Database connection utilities for the FastAPI backend.

Uses SQLAlchemy 2.x with the PyMySQL driver.

Environment variables expected (provided by the 'database' container):
- MYSQL_URL
- MYSQL_USER
- MYSQL_PASSWORD
- MYSQL_DB
- MYSQL_PORT
"""

from __future__ import annotations

import os
from typing import Generator, Optional
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker


def _normalize_mysql_host(raw: Optional[str]) -> str:
    """
    Normalize MYSQL_URL into a host name.

    MYSQL_URL can be:
    - 'localhost'
    - '127.0.0.1'
    - 'mysql' (service DNS)
    - 'http://host' (we strip scheme)
    - 'host:port' (we strip :port because port comes from MYSQL_PORT)
    """
    if not raw:
        return "localhost"

    host = raw.strip()

    # Strip scheme if present
    if "://" in host:
        host = host.split("://", 1)[1]

    # Strip any path if present
    if "/" in host:
        host = host.split("/", 1)[0]

    # If "host:port" is provided, keep only host portion because MYSQL_PORT is separate.
    if ":" in host:
        host = host.split(":", 1)[0]

    return host or "localhost"


def _build_sqlalchemy_mysql_url() -> str:
    """Build a SQLAlchemy MySQL URL from environment variables."""
    mysql_host = _normalize_mysql_host(os.getenv("MYSQL_URL"))
    mysql_user = os.getenv("MYSQL_USER")
    mysql_password = os.getenv("MYSQL_PASSWORD")
    mysql_db = os.getenv("MYSQL_DB")
    mysql_port = os.getenv("MYSQL_PORT")

    missing = [
        k
        for k, v in {
            "MYSQL_USER": mysql_user,
            "MYSQL_PASSWORD": mysql_password,
            "MYSQL_DB": mysql_db,
            "MYSQL_PORT": mysql_port,
        }.items()
        if not v
    ]
    if missing:
        # Raise ValueError so app startup fails loudly/misconfiguration is obvious.
        raise ValueError(
            "Missing required database environment variables: " + ", ".join(missing)
        )

    # quote_plus to handle special chars in passwords.
    return (
        "mysql+pymysql://"
        f"{quote_plus(mysql_user)}:{quote_plus(mysql_password)}"
        f"@{mysql_host}:{int(mysql_port)}/{mysql_db}"
        "?charset=utf8mb4"
    )


_ENGINE: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None


# PUBLIC_INTERFACE
def get_engine() -> Engine:
    """Return a singleton SQLAlchemy Engine configured from env vars."""
    global _ENGINE, _SessionLocal
    if _ENGINE is None:
        url = _build_sqlalchemy_mysql_url()
        _ENGINE = create_engine(
            url,
            pool_pre_ping=True,
            pool_recycle=3600,
            future=True,
        )
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=_ENGINE,
            future=True,
        )
    return _ENGINE


# PUBLIC_INTERFACE
def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session and ensures it's closed."""
    if _SessionLocal is None:
        get_engine()

    assert _SessionLocal is not None  # for type checkers
    db = _SessionLocal()
    try:
        yield db
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    finally:
        db.close()
