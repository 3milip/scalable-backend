import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "backend"))
sys.path.insert(0, str(_ROOT))

from app.db import Base, SessionLocal, engine, init_db
from app.models import Problem, Test
from app.results import meta_from_sample

JSON_PATH = Path("data/local_problems.json")


def main() -> None:
    if not JSON_PATH.exists():
        raise FileNotFoundError(
            f"Brak {JSON_PATH}. Najpierw musi istnieć plik z zadaniami."
        )

    Base.metadata.drop_all(bind=engine)
    init_db()
    records = json.loads(JSON_PATH.read_text(encoding="utf-8"))

    db = SessionLocal()
    try:
        for item in records:
            problem = Problem(
                external_id=item["external_id"],
                title=item["title"],
                statement=item["statement"],
                difficulty=item.get("difficulty"),
                tags=item.get("tags", []),
                source=item.get("source", "local"),
                time_limit_ms=item["time_limit_ms"],
                memory_limit_mb=item["memory_limit_mb"],
                solution=item.get("solution", ""),
                checker=item.get("checker", "exact"),
                checker_code=item.get("checker_code", ""),
            )
            db.add(problem)
            db.flush()

            for index, test in enumerate(item.get("tests", [])):
                hidden = test.get("hidden", False)
                group, max_score = meta_from_sample(
                    hidden,
                    group=test.get("group"),
                    max_score=test.get("max_score"),
                    position=index,
                )
                db.add(
                    Test(
                        problem_id=problem.id,
                        input_text=test["input"],
                        output_text=test["output"],
                        hidden=hidden,
                        position=index,
                        group=group,
                        max_score=max_score,
                    )
                )

        db.commit()
        print(f"Zaimportowano {len(records)} zadań z testami")
    finally:
        db.close()


if __name__ == "__main__":
    main()
