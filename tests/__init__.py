import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for extra in (_ROOT, _ROOT / "backend"):
    path = str(extra)
    if path not in sys.path:
        sys.path.insert(0, path)
