# Backend

Publiczne API zadań i zgłoszeń. Własna baza SQLite. Sędziego nie ma tutaj — job idzie HTTP do sprawdzarki. Język zgłoszeń: **C++** (`cpp`).

Port: **8000**.

## Setup

Z katalogu `backend/`:

```powershell
pip install -r requirements.txt
python scripts/import_problems.py
```

Import kasuje bazę i wczytuje `data/local_problems.json`.

Env (domyślne wystarczą lokalnie):

- `SPRAWDZARKA_URL` = `http://127.0.0.1:8002`
- `SERVICE_KEY` = `dev-service-key` (ten sam w sprawdzarce)
- `DATABASE_URL` = `sqlite:///./data/app.db`

## Uruchomienie

```powershell
Set-Location backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- zdrowie: http://127.0.0.1:8000/health
- docs: http://127.0.0.1:8000/docs

Bez sprawdzarki (`:8002` + worker) zgłoszenie od razu dostaje `failed`.

## Testy

Z katalogu `backend/`:

```powershell
python -m unittest discover -s tests -v
```
