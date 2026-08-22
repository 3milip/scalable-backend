def apply(ns: dict) -> None:
    ns["INSTALLED_APPS"] = ("oioioi.adapter_report",) + ns["INSTALLED_APPS"]
