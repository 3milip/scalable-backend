# Backend

FastAPI, port **8000**. Konta, zadania, zgłoszenia. Sędziego woła na `:8002`.

```powershell
Set-Location C:\Users\emilk\repoprojekt\scalable-backend
$env:PYTHONPATH = "backend"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Env (opcjonalnie): `SERVICE_KEY`, `SPRAWDZARKA_URL`, `PUBLIC_CALLBACK_BASE`.
Kontrakt: [CONTRACT.md](CONTRACT.md)
