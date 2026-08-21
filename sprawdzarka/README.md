# Sprawdzarka

Kolejka jobów, izolacja w Dockerze, sędzia C++ (`g++` w obrazie `gcc:13-bookworm`). Własna baza SQLite. Gada z backendem po HTTP.

Port: **8002**.

## Setup

Z katalogu `sprawdzarka/`:

```powershell
pip install -r requirements.txt
python -m sprawdzarka.pull_images
```

Env (domyślne wystarczą lokalnie):

- `BACKEND_URL` = `http://127.0.0.1:8000`
- `SERVICE_KEY` = `dev-service-key`
- `DATABASE_URL` = `sqlite:///./data/jobs.db`

## Uruchomienie

Terminal A — API:

```powershell
Set-Location sprawdzarka
uvicorn sprawdzarka.main:app --reload --host 127.0.0.1 --port 8002
```

Terminal B — worker (bez tego joby wiszą w `queued`):

```powershell
Set-Location sprawdzarka
python -m sprawdzarka.worker
```

Zdrowie: http://127.0.0.1:8002/health

Worker wymaga Dockera (na Windowsie: Docker Desktop + WSL 2).

## Testy

Z katalogu `sprawdzarka/`:

```powershell
python -m unittest discover -s tests -v
```
