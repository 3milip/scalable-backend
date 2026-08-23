def apply(ns: dict) -> None:
    ns["INSTALLED_APPS"] = ("oioioi.adapter_report",) + ns["INSTALLED_APPS"]
    # Obraz GHCR ma USE_UNSAFE_EXEC=True (goły ulimit, RAM=0).
    # False → web ustawia exec_mode=sio2jail na nowych jobach.
    ns["USE_UNSAFE_EXEC"] = False
    ns["DEFAULT_SAFE_EXECUTION_MODE"] = "sio2jail"
