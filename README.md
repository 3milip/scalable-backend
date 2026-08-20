# scalable-backend

Trzy osobne aplikacje, które gadają ze sobą po HTTP. Nie współdzielą bazy ani importów Pythona.

| | port | start |
|---|---|---|
| [frontend](frontend/README.md) | :3000 | `cd frontend; python -m http.server 3000` |
| [backend](backend/README.md) | :8000 | `cd backend; uvicorn app.main:app --port 8000` |
| [sprawdzarka](sprawdzarka/README.md) | :8002 | API: `cd sprawdzarka; uvicorn sprawdzarka.main:app --port 8002` · worker: `python -m sprawdzarka.worker` |

Przeglądarka → frontend → backend → sprawdzarka (Docker). Wynik wraca callbackiem na backend.

Kontrakty: [backend/CONTRACT.md](backend/CONTRACT.md), [sprawdzarka/CONTRACT.md](sprawdzarka/CONTRACT.md).

## Setup (raz)

Wymagane: Python 3.12+, Docker Desktop (WSL 2) dla workera.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
pip install -r sprawdzarka/requirements.txt
Set-Location backend; python scripts/import_problems.py
Set-Location ..\sprawdzarka; python -m sprawdzarka.pull_images
```

`SERVICE_KEY` ten sam w backendzie i sprawdzarce (domyślnie `dev-service-key`).

## Odpalenie

Cztery okna (z włączonym `.venv`):

1. `cd frontend; python -m http.server 3000`
2. `cd backend; uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`
3. `cd sprawdzarka; uvicorn sprawdzarka.main:app --reload --host 127.0.0.1 --port 8002`
4. `cd sprawdzarka; python -m sprawdzarka.worker`

Strona: http://127.0.0.1:3000/

## Testy

```powershell
Set-Location backend; python -m unittest discover -s tests -v
Set-Location ..\sprawdzarka; python -m unittest discover -s tests -v
```
