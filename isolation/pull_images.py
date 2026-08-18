#!/usr/bin/env python3
"""Pobiera obrazy Dockera sędziego, zanim ruszy pierwszy job."""

import argparse
import os
import subprocess
import sys

DEFAULT_IMAGE = "python:3.12-slim-bookworm"


def docker_prefix() -> list[str]:
    if os.name == "nt":
        return ["wsl", "-e", "docker"]
    return ["docker"]


def needed_images() -> list[str]:
    images: list[str] = []
    for raw in (
        os.environ.get("ISOLATE_IMAGE", DEFAULT_IMAGE),
        *os.environ.get("ISOLATE_ALLOWED_IMAGES", "").split(),
    ):
        name = raw.strip()
        if name and name not in images:
            images.append(name)
    return images


def image_present(image: str) -> bool:
    result = subprocess.run(
        [*docker_prefix(), "image", "inspect", image],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def docker_running() -> bool:
    try:
        result = subprocess.run(
            [*docker_prefix(), "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return False
    return result.returncode == 0


def pull(image: str) -> None:
    print(f"pobieram {image} ...", flush=True)
    result = subprocess.run([*docker_prefix(), "pull", image])
    if result.returncode != 0:
        print(f"Błąd: nie udało się pobrać {image}", file=sys.stderr)
        raise SystemExit(result.returncode or 1)
    print(f"gotowe: {image}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pobierz obrazy Dockera potrzebne do izolacji (przed pierwszym jobem)."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="pobierz nawet gdy obraz już jest lokalnie",
    )
    args = parser.parse_args()

    if not docker_running():
        print("Błąd: Docker nie działa (na Windowsie potrzebny WSL).", file=sys.stderr)
        raise SystemExit(1)

    for image in needed_images():
        if not args.force and image_present(image):
            print(f"jest: {image}", flush=True)
            continue
        pull(image)

    print("obrazy sędziego gotowe", flush=True)


if __name__ == "__main__":
    main()
