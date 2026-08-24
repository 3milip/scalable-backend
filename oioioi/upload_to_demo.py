"""Uruchamiać w kontenerze web: python manage.py shell < upload_to_demo.py nie;
lepiej: exec python -c nie. Wpinamy przez stdin manage.py shell.
"""

from pathlib import Path

from django.core.management import call_command

from oioioi.contests.models import Contest, ProblemInstance, Round
from oioioi.problems.models import Problem
from oioioi.problems.utils import get_new_problem_instance, update_tests_from_main_pi

PKG = Path("/tmp/oioioi_packages")
contest = Contest.objects.get(id="demo")
rnd = Round.objects.filter(contest=contest).order_by("id").first()
if rnd is None:
    raise SystemExit("brak rundy w contestcie demo")

lines = (PKG / "id_map.txt").read_text(encoding="utf-8").splitlines()
ok = 0
for line in lines:
    line = line.strip()
    if not line:
        continue
    external_id, sinol_id, zipname = [part.strip() for part in line.split("\t")]
    zip_path = PKG / zipname
    if not zip_path.is_file():
        print("BRAK", zip_path)
        continue
    existing = ProblemInstance.objects.filter(contest=contest, short_name=external_id).first()
    try:
        if existing:
            print("UPDATE", external_id, "problem", existing.problem_id)
            call_command("updateproblem", existing.problem_id, str(zip_path))
            existing.problem.short_name = external_id
            existing.problem.save(update_fields=["short_name"])
            update_tests_from_main_pi(existing)
            existing.round = rnd
            existing.short_name = external_id
            existing.save()
        else:
            print("ADD", external_id, zipname)
            call_command("addproblem", str(zip_path))
            problem = Problem.objects.filter(short_name=sinol_id).order_by("-id").first()
            if problem is None:
                print("  FAIL brak Problem", sinol_id)
                continue
            problem.short_name = external_id
            problem.save(update_fields=["short_name"])
            pi = (
                ProblemInstance.objects.filter(contest=contest, problem=problem).first()
                or get_new_problem_instance(problem, contest)
            )
            pi.round = rnd
            pi.short_name = external_id
            pi.save()
            print("  PI", pi.id, pi.short_name)
        ok += 1
    except Exception as error:
        print("FAIL", external_id, type(error).__name__, error)

print("DONE", ok, "/", len([ln for ln in lines if ln.strip()]))
names = list(
    ProblemInstance.objects.filter(contest=contest).order_by("short_name").values_list("short_name", flat=True)
)
print("CONTEST", names)
