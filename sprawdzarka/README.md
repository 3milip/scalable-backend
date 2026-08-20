# Sprawdzarka

HTTP na **8002**, OIOIOI Docker na **8001**. Konto serwisowe `judgebot`, callback na backend.

```powershell
Set-Location C:\Users\emilk\repoprojekt\scalable-backend\oioioi
docker compose up
```

Drugie okno:

Z katalogu repo (pakiet `sprawdzarka`):

```powershell
Set-Location C:\Users\emilk\repoprojekt\scalable-backend
$env:SERVICE_KEY = "dev-service-key"
.\.venv\Scripts\python.exe -m uvicorn sprawdzarka.main:app --reload --host 127.0.0.1 --port 8002
```

Albo z folderu aplikacji (`uvicorn main:app` — `_path.py` dopina korzeń repo):

```powershell
Set-Location C:\Users\emilk\repoprojekt\scalable-backend\sprawdzarka
$env:SERVICE_KEY = "dev-service-key"
..\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8002
```

(z aktywowanym venv: `python -m uvicorn main:app --reload --host 127.0.0.1 --port 8002`)

Raz: `python scripts/push_to_oioioi.py` albo `POST /problems/sync`.
Kontrakt: [CONTRACT.md](CONTRACT.md)
