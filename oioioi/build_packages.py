"""Buduje paczki SINOL z backend/data/local_problems.json."""

from __future__ import annotations

import json
import re
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
JSON_PATH = ROOT.parent / "backend" / "data" / "local_problems.json"
PACKAGES = ROOT / "packages"


def sinol_id(external_id: str) -> str:
    # Prefiks plików .in może być tylko literami: local020.in → "local", nie "local02".
    if re.fullmatch(r"[a-zA-Z_]+", external_id):
        return external_id
    match = re.fullmatch(r"local-(\d+)", external_id)
    if match:
        return "loc" + suffix(int(match.group(1)) - 1)
    cleaned = re.sub(r"[^a-zA-Z_]", "", external_id)
    if not cleaned:
        raise ValueError(f"pusty sinol_id z {external_id!r}")
    return cleaned


def suffix(index: int) -> str:
    if index < 26:
        return chr(ord("a") + index)
    q, r = divmod(index, 26)
    return suffix(q - 1) + chr(ord("a") + r)


def write_io(path: Path, text: str) -> None:
    path.write_text(text.replace("\r\n", "\n"), encoding="utf-8", newline="\n")


def build_one(item: dict) -> Path:
    external_id = str(item["external_id"])
    task = sinol_id(external_id)
    dest = PACKAGES / task
    if dest.exists():
        shutil.rmtree(dest)
    (dest / "in").mkdir(parents=True)
    (dest / "out").mkdir()
    (dest / "prog").mkdir()

    memory_kb = int(item["memory_limit_mb"]) * 1024
    time_ms = int(item["time_limit_ms"])
    title = str(item["title"]).replace('"', "'")
    (dest / "config.yml").write_text(
        (
            f"title: {title}\n"
            f"sinol_task_id: {task}\n"
            f"memory_limit: {memory_kb}\n"
            f"time_limit: {time_ms}\n"
            "no_outgen: true\n"
            "scores:\n"
            "  1: 100\n"
        ),
        encoding="utf-8",
        newline="\n",
    )

    examples = [t for t in item.get("tests", []) if not t.get("hidden")]
    hidden = [t for t in item.get("tests", []) if t.get("hidden")]
    if not hidden:
        hidden = examples
        examples = []

    for i, test in enumerate(examples):
        name = f"{task}0" if i == 0 else f"{task}0{suffix(i - 1)}"
        write_io(dest / "in" / f"{name}.in", test["input"])
        write_io(dest / "out" / f"{name}.out", test["output"])
    for i, test in enumerate(hidden):
        name = f"{task}1{suffix(i)}"
        write_io(dest / "in" / f"{name}.in", test["input"])
        write_io(dest / "out" / f"{name}.out", test["output"])

    solution = item.get("solution") or ""
    (dest / "prog" / f"{task}.cpp").write_text(solution, encoding="utf-8", newline="\n")

    zip_path = PACKAGES / f"{task}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for folder in ("", "in", "out", "prog"):
            name = f"{task}/" if not folder else f"{task}/{folder}/"
            info = zipfile.ZipInfo(name)
            info.external_attr = 0o40755 << 16
            zf.writestr(info, "")
        for file in dest.rglob("*"):
            if file.is_file():
                zf.write(file, arcname=f"{task}/{file.relative_to(dest).as_posix()}")
    return zip_path


def main() -> None:
    records = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    PACKAGES.mkdir(exist_ok=True)
    mapping = []
    for item in records:
        zip_path = build_one(item)
        mapping.append((item["external_id"], sinol_id(item["external_id"]), zip_path.name))
        print(f"{item['external_id']} -> {zip_path.name}")
    (PACKAGES / "id_map.txt").write_text(
        "\n".join(f"{ext}\t{sid}\t{zipn}" for ext, sid, zipn in mapping) + "\n",
        encoding="utf-8",
    )
    print(f"zbudowano {len(mapping)} paczek")


if __name__ == "__main__":
    main()
