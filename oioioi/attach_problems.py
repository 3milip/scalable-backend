"""Uruchamiane wewnątrz kontenera web: addproblem/updateproblem + contest local."""

from __future__ import annotations

import os
import sys
from io import StringIO
from pathlib import Path

os.chdir("/sio2/deployment")
sys.path.insert(0, "/sio2/deployment")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

import django

django.setup()

from django.contrib.auth.models import User
from django.core.management import call_command
from oioioi.contests.models import Contest, ContestPermission, RegistrationAvailabilityConfig, Round
from oioioi.problems.models import Problem
from oioioi.problems.utils import get_new_problem_instance

PACK_DIR = Path(os.environ.get("SINOLPACK_DIR", "/tmp/sinolpack"))
CONTEST_ID = os.environ.get("OIOIOI_CONTEST_ID", "local")
CONTEST_NAME = os.environ.get("OIOIOI_CONTEST_NAME", "Laboratorium")


def ensure_admin() -> None:
    try:
        call_command(
            "loaddata",
            "/sio2/oioioi/extra/dbdata/default_admin.json",
            verbosity=0,
        )
    except Exception as error:
        print(f"admin fixture: {error}", file=sys.stderr)


def ensure_contest() -> tuple[Contest, Round]:
    contest, created = Contest.objects.get_or_create(
        id=CONTEST_ID,
        defaults={
            "name": CONTEST_NAME,
            "controller_name": "oioioi.programs.controllers.ProgrammingContestController",
        },
    )
    if created:
        print(f"contest {CONTEST_ID} created")
    admin = User.objects.filter(username="admin").first()
    if admin is not None:
        ContestPermission.objects.get_or_create(
            user=admin,
            contest=contest,
            permission="contests.contest_admin",
        )
    round_obj = contest.round_set.order_by("id").first()
    if round_obj is None:
        round_obj = contest.round_set.create(name="Runda 1")
        print("round created")
    from django.utils import timezone

    now = timezone.now()
    changed = False
    if round_obj.results_date is None:
        round_obj.results_date = round_obj.start_date or now
        changed = True
    if getattr(round_obj, "public_results_date", None) is None and hasattr(round_obj, "public_results_date"):
        round_obj.public_results_date = round_obj.results_date
        changed = True
    if changed:
        round_obj.save()
        print("round results_date set")
    RegistrationAvailabilityConfig.objects.get_or_create(
        contest=contest,
        defaults={"enabled": "YES"},
    )
    return contest, round_obj


def unpack_zip(path: Path) -> Problem:
    short = path.stem
    existing = Problem.objects.filter(short_name=short).first()
    out = StringIO()
    if existing is not None:
        call_command("updateproblem", str(existing.id), str(path), stdout=out)
        existing.refresh_from_db()
        print(f"updated {short} id={existing.id}")
        return existing
    call_command("addproblem", str(path), stdout=out)
    raw = out.getvalue().strip().splitlines()[-1].strip()
    problem = Problem.objects.get(id=int(raw))
    print(f"added {short} id={problem.id}")
    return problem


def attach(problem: Problem, contest: Contest, round_obj: Round) -> None:
    pi = problem.probleminstance_set.filter(contest=contest).first()
    if pi is not None:
        if pi.round_id is None:
            pi.round = round_obj
            pi.save(update_fields=["round"])
        return
    pi = get_new_problem_instance(problem, contest)
    pi.short_name = problem.short_name
    pi.round = round_obj
    pi.save()
    print(f"attached {problem.short_name} to {contest.id}")


def main() -> int:
    ensure_admin()
    contest, round_obj = ensure_contest()
    zips = sorted({*PACK_DIR.glob("*.zip"), *PACK_DIR.glob("*/*.zip")})
    if not zips:
        print(f"brak zipów w {PACK_DIR}", file=sys.stderr)
        return 1
    failed = 0
    for path in zips:
        try:
            problem = unpack_zip(path)
            attach(problem, contest, round_obj)
        except Exception as error:
            failed += 1
            print(f"FAIL {path.name}: {error}", file=sys.stderr)
    print(f"gotowe, contest /c/{contest.id}/  (błędy: {failed}/{len(zips)})")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
