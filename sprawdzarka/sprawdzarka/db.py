import os
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./data/jobs.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 5},
)

SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def sqlite_path() -> Path:
    database = engine.url.database
    if not database:
        raise RuntimeError("DATABASE_URL musi wskazywać plik SQLite")
    path = Path(database)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from sprawdzarka.models import Job, Worker  # noqa: F401

    sqlite_path().parent.mkdir(parents=True, exist_ok=True)
    with engine.begin() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
        conn.execute(text("PRAGMA busy_timeout=5000"))
    Base.metadata.create_all(bind=engine)
