import sqlite3 as sq
from pathlib import Path
from typing import Any, Generator

from fastapi import Request
from sqlalchemy import URL, create_engine
from sqlalchemy.orm import Session


def build_engine(database_path: Path):
    return create_engine(
        URL.create("sqlite", database=str(database_path)),
        connect_args={
            "check_same_thread": False,
            "timeout": 60,
            "autocommit": sq.LEGACY_TRANSACTION_CONTROL,
        },
    )


def get_session(request: Request) -> Generator[Session, Any, None]:
    with Session(request.app.state.engine) as session:
        yield session
