from django.db.models import Max
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status, views
from rest_framework.response import Response

from oioioi.contests.api import CanEnterContest, UnsafeApiAllowed
from oioioi.contests.models import Contest, SubmissionReport
from oioioi.programs.models import ProgramSubmission, TestReport

# INI_OK na zgłoszeniu = przykłady. Karty biorą NORMAL/FULL/FINAL.
FINAL_KINDS = ("NORMAL", "FULL", "FINAL")
EARLY_FAIL = frozenset({"CE", "SE", "INI_ERR", "ERR"})


def _score_int(value):
    if value is None:
        return None
    if hasattr(value, "to_int"):
        return value.to_int()
    return int(value)


def _pick_final(reports):
    by_kind = {report.kind: report for report in reports}
    for kind in FINAL_KINDS:
        if kind in by_kind:
            return by_kind[kind]
    return None


def _verdict(submission, final, initial):
    for report in (final, initial):
        if report is None:
            continue
        score_report = report.score_report
        if score_report is not None and score_report.status:
            return score_report.status
    return submission.status


class GetSubmissionReport(views.APIView):
    """Źródło kart: werdykt/punkty/czas/RAM z raportu końcowego, nie z listy."""

    permission_classes = (permissions.IsAuthenticated, CanEnterContest, UnsafeApiAllowed)

    def get(self, request, contest_id, submission_id):
        contest = get_object_or_404(Contest, id=contest_id)
        submission = get_object_or_404(
            ProgramSubmission,
            id=submission_id,
            problem_instance__contest=contest,
        )
        if submission.user != request.user and not request.user.is_superuser:
            raise Http404("Submission not found.")

        reports = list(
            SubmissionReport.objects.filter(
                submission=submission,
                status="ACTIVE",
                kind__in=("INITIAL",) + FINAL_KINDS,
            )
        )
        initial = next((r for r in reports if r.kind == "INITIAL"), None)
        final = _pick_final(reports)
        scored = TestReport.objects.filter(submission_report=final) if final else TestReport.objects.none()
        time_ms = scored.aggregate(Max("time_used"))["time_used__max"]
        memory_kb = scored.filter(mem_used__gt=0).aggregate(Max("mem_used"))["mem_used__max"]

        score = None
        max_score = None
        if final is not None and final.score_report is not None:
            score = _score_int(final.score_report.score)
            max_score = _score_int(final.score_report.max_score)
        elif submission.score is not None:
            score = _score_int(submission.score)
            max_score = _score_int(submission.max_score)

        complete = final is not None or submission.status in EARLY_FAIL
        return Response(
            {
                "id": submission.id,
                "status": submission.status,
                "verdict": _verdict(submission, final, initial),
                "score": score,
                "max_score": max_score,
                "time_ms": time_ms,
                "memory_kb": memory_kb,
                "complete": complete,
            },
            status=status.HTTP_200_OK,
        )
