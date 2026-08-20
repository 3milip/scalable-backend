# scalable-backend

Trzy osobne aplikacje (HTTP):

| | port | start |
|---|---|---|
| [frontend](frontend/README.md) | :3000 | `cd frontend; npm run dev` |
| [backend](backend/README.md) | :8000 | `PYTHONPATH=backend uvicorn app.main:app --port 8000` |
| [sprawdzarka](sprawdzarka/README.md) | :8002 | z repo: `uvicorn sprawdzarka.main:app --port 8002` · z folderu: `uvicorn main:app --port 8002` |
| OIOIOI (w środku sprawdzarki) | :8001 | `cd oioioi; docker compose up` |

Przeglądarka → frontend → backend → sprawdzarka → OIOIOI. Wynik wraca callbackiem. Język: **C++**.

Kontrakty: [CONTRACTS.md](CONTRACTS.md). Isolation (`isolation/`) zostaje do testów kolejki, poza żywą ścieżką.

## Setup (raz)

```powershell
Set-Location C:\Users\emilk\repoprojekt\scalable-backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/import_problems.py
python scripts/push_to_oioioi.py
Set-Location frontend; npm install
```

`SERVICE_KEY` ten sam w backendzie i sprawdzarce (domyślnie `dev-service-key`).
