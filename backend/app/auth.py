import os

from fastapi import Header, HTTPException

SERVICE_KEY = os.environ.get("SERVICE_KEY", "dev-service-key")


def require_service_key(
    x_service_key: str | None = Header(default=None, alias="X-Service-Key"),
) -> None:
    if x_service_key != SERVICE_KEY:
        raise HTTPException(status_code=401, detail="Niepoprawny klucz")
