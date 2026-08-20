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
    """WAL, create_all, brakujące kolumny na istniejącym pliku."""
    from app.models import Job, SubmissionResult, User, Worker  # noqa: F401

    sqlite_path().parent.mkdir(parents=True, exist_ok=True)
    with engine.begin() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
        conn.execute(text("PRAGMA busy_timeout=5000"))
    Base.metadata.create_all(bind=engine)
    _migrate_submissions()
    _migrate_tests()
    _migrate_problems()
    _split_v1_hidden_groups()
    _rescore_done_submissions()
    _backfill_jobs()


def _migrate_submissions() -> None:
    additions = {
        "priority": "INTEGER NOT NULL DEFAULT 0",
        "attempts": "INTEGER NOT NULL DEFAULT 0",
        "worker_id": "VARCHAR(64)",
        "heartbeat_at": "INTEGER",
        "last_error": "TEXT",
        "score": "INTEGER",
        "max_score": "INTEGER NOT NULL DEFAULT 0",
        "user_id": "INTEGER",
        "oioioi_id": "INTEGER",
        "judge_job_id": "VARCHAR(64)",
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


def _split_v1_hidden_groups() -> None:
    """Stary seed: wszystkie ukryte w grupie 1. Każdy test → grupa = pozycja."""
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE tests
                SET "group" = CAST(position AS TEXT)
                WHERE hidden = 1 AND "group" = '1' AND position != 1
                """
            )
        )


def _rescore_done_submissions() -> None:
    """Przelicz score/max po zmianie grup, bez ponownego sędziowania."""
    from sqlalchemy.orm import Session

    from app.models import Submission, SubmissionResult, Test
    from app.results import problem_max_score, score_groups, test_points

    db = Session(engine)
    try:
        tests_all = db.query(Test).all()
        by_problem: dict[int, list[Test]] = {}
        by_id: dict[int, Test] = {}
        for test in tests_all:
            by_problem.setdefault(test.problem_id, []).append(test)
            by_id[test.id] = test
        for sub in db.query(Submission).filter(Submission.status == "done").all():
            tests = by_problem.get(sub.problem_id, [])
            sub.max_score = problem_max_score(tests)
            scored: list[tuple[str, str, int]] = []
            for row in (
                db.query(SubmissionResult)
                .filter(SubmissionResult.submission_id == sub.id)
                .all()
            ):
                test = by_id.get(row.test_id)
                if test is None:
                    continue
                row.score = test_points(row.verdict, test.max_score)
                scored.append((test.group, row.verdict, test.max_score))
            if scored:
                sub.score = score_groups(scored)
        db.commit()
    finally:
        db.close()


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


def _backfill_jobs() -> None:
    """Queued zgłoszenia bez otwartego joba — po starcie na starej bazie."""
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO jobs (submission_id, kind, status, priority, attempts)
                SELECT s.id, 'judge', 'queued', COALESCE(s.priority, 0), 0
                FROM submissions s
                WHERE s.status = 'queued'
                  AND NOT EXISTS (
                      SELECT 1 FROM jobs j
                      WHERE j.submission_id = s.id
                        AND j.kind = 'judge'
                        AND j.status IN ('queued', 'leased')
                  )
                """
            )
        )
