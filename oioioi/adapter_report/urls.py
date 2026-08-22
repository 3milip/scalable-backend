from django.urls import re_path

from oioioi.adapter_report import api

noncontest_patterns = [
    re_path(
        r"^api/c/(?P<contest_id>[a-z0-9_-]+)/submission_report/(?P<submission_id>\d+)/$",
        api.GetSubmissionReport.as_view(),
        name="api_submission_report",
    ),
]
