import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "backend"))
sys.path.insert(0, str(_ROOT))

from app.sinolpack import export_json


def main() -> None:
    paths = export_json()
    print(f"Zapisano {len(paths)} paczek w data/sinolpack/")
    for path in paths:
        print(f"  {path}")
    print("Wgranie: python scripts/push_to_oioioi.py")


if __name__ == "__main__":
    main()
