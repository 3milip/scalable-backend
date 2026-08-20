"""Paczki sinolpack z `data/local_problems.json` — do wgrania w OIOIOI."""

from __future__ import annotations

import json
import re
import zipfile
from io import BytesIO
from pathlib import Path

from app.results import meta_from_sample

JSON_PATH = Path("data/local_problems.json")


def short_name_for(external_id: str) -> str:
    """SINOL: prefiks plików to tylko litery. `local-01` → `loca`."""
    digits = "".join(c for c in external_id if c.isdigit())
    n = int(digits) if digits else 1
    if n < 1:
        n = 1
    suffix = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        suffix = chr(ord("a") + rem) + suffix
    name = "loc" + suffix
    if not re.fullmatch(r"[a-zA-Z_]+", name):
        raise ValueError(f"Nie da się zrobić short_name z {external_id!r}")
    return name


def _yaml_escape(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def config_yml(item: dict, scored: dict[str, int]) -> str:
    lines = [
        f"title: {_yaml_escape(item['title'])}",
        f"time_limit: {int(item['time_limit_ms'])}",
        f"memory_limit: {int(item['memory_limit_mb']) * 1024}",
        "no_outgen: true",
    ]
    if scored:
        lines.append("scores:")
        for group in sorted(scored, key=lambda g: (len(g), g)):
            lines.append(f"  {group}: {scored[group]}")
    lines.append("")
    return "\n".join(lines)


def _test_basename(short: str, hidden: bool, position: int, example_index: int) -> tuple[str, str]:
    """Nazwa pliku bez rozszerzenia + grupa punktowana (pusta dla przykładu)."""
    if not hidden:
        suffix = "" if example_index == 0 else chr(ord("a") + example_index - 1)
        return f"{short}0{suffix}", ""
    return f"{short}{position}", str(position)


def files_for_problem(item: dict) -> dict[str, bytes]:
    short = short_name_for(item["external_id"])
    files: dict[str, bytes] = {}
    scored: dict[str, int] = {}
    example_index = 0

    for position, test in enumerate(item.get("tests", [])):
        hidden = bool(test.get("hidden", False))
        group, max_score = meta_from_sample(
            hidden,
            group=test.get("group"),
            max_score=test.get("max_score"),
            position=position,
        )
        basename, _ = _test_basename(short, hidden, position, example_index)
        if hidden:
            scored[str(group)] = max_score
            basename = f"{short}{group}"
        else:
            example_index += 1
        files[f"{short}/in/{basename}.in"] = test["input"].encode("utf-8")
        files[f"{short}/out/{basename}.out"] = test["output"].encode("utf-8")

    files[f"{short}/config.yml"] = config_yml(item, scored).encode("utf-8")
    files[f"{short}/attachments/tresc.txt"] = item.get("statement", "").encode("utf-8")
    solution = item.get("solution") or ""
    if solution.strip():
        files[f"{short}/prog/{short}.cpp"] = solution.encode("utf-8")
        files[f"{short}/attachments/wzorcowka.cpp"] = solution.encode("utf-8")
    return files


def zip_problem(item: dict) -> bytes:
    buf = BytesIO()
    files = files_for_problem(item)
    dirs = {f"{p.split('/')[0]}/" for p in files}
    for path in files:
        parts = path.split("/")
        for i in range(1, len(parts)):
            dirs.add("/".join(parts[:i]) + "/")
    if files:
        dirs.add(f"{next(iter(files)).split('/')[0]}/prog/")
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
        for directory in sorted(dirs):
            archive.writestr(directory, b"")
        for name, data in files.items():
            archive.writestr(name, data)
    return buf.getvalue()


def export_json(json_path: Path = JSON_PATH, dest: Path = Path("data/sinolpack")) -> list[Path]:
    records = json.loads(json_path.read_text(encoding="utf-8"))
    dest.mkdir(parents=True, exist_ok=True)
    for old in dest.glob("*.zip"):
        old.unlink()
    written: list[Path] = []
    for item in records:
        path = dest / f"{short_name_for(item['external_id'])}.zip"
        path.write_bytes(zip_problem(item))
        written.append(path)
    return written
