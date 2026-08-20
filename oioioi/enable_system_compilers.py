"""W kontenerze web: kompilatory systemowe (g++ z obrazu), bez sandboxów 4.8.2."""

from pathlib import Path

SETTINGS = Path("/sio2/deployment/settings.py")
OLD = (
    "# AVAILABLE_COMPILERS = SYSTEM_COMPILERS\n"
    "# DEFAULT_COMPILERS = SYSTEM_DEFAULT_COMPILERS"
)
NEW = (
    "AVAILABLE_COMPILERS = SYSTEM_COMPILERS\n"
    "DEFAULT_COMPILERS = SYSTEM_DEFAULT_COMPILERS"
)


def main() -> int:
    text = SETTINGS.read_text(encoding="utf-8")
    if NEW in text and OLD not in text:
        print("system compilers already on")
        return 0
    if OLD not in text:
        print("nie znalazłem zakomentowanych SYSTEM_COMPILERS", flush=True)
        return 1
    SETTINGS.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    print("system compilers enabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
