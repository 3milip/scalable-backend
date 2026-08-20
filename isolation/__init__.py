# Pakiet: kolejka jobów + izolacja Dockera.
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_backend = str(_ROOT / "backend")
if _backend not in sys.path:
    sys.path.insert(0, _backend)

