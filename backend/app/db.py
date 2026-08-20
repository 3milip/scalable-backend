import os
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./data/app.db")

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
    from app.models import Problem, Submission, SubmissionResult, Test  # noqa: F401

    sqlite_path().parent.mkdir(parents=True, exist_ok=True)
    with engine.begin() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
        conn.execute(text("PRAGMA busy_timeout=5000"))
    Base.metadata.create_all(bind=engine)
    _migrate_submissions()
    _migrate_tests()
    _migrate_problems()


def _migrate_submissions() -> None:
    additions = {
        "score": "INTEGER",
        "max_score": "INTEGER NOT NULL DEFAULT 0",
    }
    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(submissions)")).fetchall()
        existing = {row[1] for row in rows}
        for name, ddl in additions.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE submissions ADD COLUMN {name} {ddl}"))


def _migrate_tests() -> None:
    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(tests)")).fetchall()
        existing = {row[1] for row in rows}
        added_group = "group" not in existing
        if added_group:
            conn.execute(text('ALTER TABLE tests ADD COLUMN "group" VARCHAR(16)'))
        if "max_score" not in existing:
            conn.execute(text("ALTER TABLE tests ADD COLUMN max_score INTEGER"))
        if added_group:
            conn.execute(
                text(
                    """
                    UPDATE tests
                    SET "group" = CASE WHEN hidden = 0 THEN '0' ELSE CAST(position AS TEXT) END,
                        max_score = CASE WHEN hidden = 0 THEN 0 ELSE 1 END
                    """
                )
            )


def _migrate_problems() -> None:
    additions = {
        "checker": "VARCHAR(16) NOT NULL DEFAULT 'exact'",
        "checker_code": "TEXT DEFAULT ''",
    }
    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(problems)")).fetchall()
        existing = {row[1] for row in rows}
        for name, ddl in additions.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE problems ADD COLUMN {name} {ddl}"))
