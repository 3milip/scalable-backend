import json
import urllib.request
from pathlib import Path

API_URL = "https://codeforces.com/api/problemset.problems"
OUT_PATH = Path("data/problems.json")
LIMIT = 100


def fetch_problems() -> list[dict]:
    with urllib.request.urlopen(API_URL, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("status") != "OK":
        raise RuntimeError("Codeforces API oddało błąd")
    return payload["result"]["problems"]


def to_record(problem: dict) -> dict:
    contest_id = problem["contestId"]
    index = problem["index"]
    return {
        "title": problem["name"],
        "statement": f"https://codeforces.com/problemset/problem/{contest_id}/{index}",
        "difficulty": problem.get("rating"),
        "tags": problem.get("tags", []),
        "source": "codeforces",
        "time_limit_ms": 1000,
        "memory_limit_mb": 256,
        "external_id": f"{contest_id}{index}",
    }


def main() -> None:
    raw = fetch_problems()
    picked = [p for p in raw if p.get("rating") is not None][:LIMIT]
    if len(picked) < LIMIT:
        raise RuntimeError(f"Mam tylko {len(picked)} zadań, potrzeba {LIMIT}")

    records = [to_record(p) for p in picked]
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Zapisano {len(records)} zadań do {OUT_PATH}")


if __name__ == "__main__":
    main()
