DONE = {"OK", "WA", "TLE", "MLE", "RE", "CE", "SE", "WA_OLE", "RV"}
PENDING = {"?", "PENDING"}


def map_status(
    oioioi_status: str | None,
    score: int | None = None,
    max_score: int | None = None,
) -> tuple[str, str | None]:
    if not oioioi_status or oioioi_status in PENDING:
        return "running", None
    if oioioi_status == "INI_ERR":
        return "done", "WA"
    if oioioi_status == "INI_OK":
        if score is None:
            return "running", None
        if max_score is not None and score < max_score:
            return "done", "WA"
        return "done", "OK"
    if oioioi_status in {"ERR", "FAILED"}:
        return "failed", None
    if oioioi_status in DONE:
        return "done", oioioi_status
    return "running", None
