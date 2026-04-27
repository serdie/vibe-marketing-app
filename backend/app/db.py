from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings

_settings = get_settings()
_url = _settings.database_url

# Asegura que el directorio del SQLite existe (volumen Fly o local)
if _url.startswith("sqlite:///"):
    db_path = _url.replace("sqlite:///", "", 1)
    if db_path and not db_path.startswith(":"):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

engine = create_engine(
    _url,
    connect_args={"check_same_thread": False} if _url.startswith("sqlite") else {},
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


@contextmanager
def session_scope() -> Iterator[Session]:
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def get_db() -> Iterator[Session]:
    with session_scope() as s:
        yield s
