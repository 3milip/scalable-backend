"""W kontenerze web: konto OIOIOI + token API + udział w contestcie local."""

from __future__ import annotations

import os
import sys

os.chdir("/sio2/deployment")
sys.path.insert(0, "/sio2/deployment")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

import django

django.setup()

from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token

from oioioi.contests.models import Contest
from oioioi.participants.models import Participant

CONTEST_ID = os.environ.get("OIOIOI_CONTEST_ID", "local")
username = os.environ.get("OIOIOI_NEW_USER", "").strip()
password = os.environ.get("OIOIOI_NEW_PASSWORD", "")

if not username or not password:
    print("missing OIOIOI_NEW_USER / OIOIOI_NEW_PASSWORD", file=sys.stderr)
    raise SystemExit(1)

user = User.objects.filter(username=username).first()
if user is None:
    user = User.objects.create_user(
        username=username,
        email=f"{username}@local.test",
        password=password,
    )
else:
    user.set_password(password)
    user.save()

contest = Contest.objects.filter(id=CONTEST_ID).first()
if contest is None:
    print(f"no contest {CONTEST_ID}", file=sys.stderr)
    raise SystemExit(2)

Participant.objects.get_or_create(contest=contest, user=user)
if os.environ.get("OIOIOI_MAKE_ADMIN", "").strip() in {"1", "true", "yes"}:
    from oioioi.contests.models import ContestPermission

    ContestPermission.objects.get_or_create(
        user=user,
        contest=contest,
        permission="contests.contest_admin",
    )
token, _ = Token.objects.get_or_create(user=user)
print(token.key)
