import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import Base, SessionLocal, engine
from app.models import Problem

JSON_PATH = Path("data/problems.json")


def main() -> None:
    if not JSON_PATH.exists():
        raise FileNotFoundError(
            f"Brak {JSON_PATH}. Najpierw odpal: python scripts/scrape_problems.py"
        )

    Base.metadata.create_all(bind=engine)
    records = json.loads(JSON_PATH.read_text(encoding="utf-8"))

    db = SessionLocal()
    try:
        added = 0
        for item in records:
            exists = db.query(Problem).filter_by(external_id=item["external_id"]).first()
            if exists:
                continue
            db.add(Problem(**item))
            added += 1
        db.commit()
        print(f"Dodano {added} zadań, pominięto {len(records) - added}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
