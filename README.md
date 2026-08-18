# scalable-backend

Backend aplikacji do zadań programowania konkursowego.

Zgłoszony kod nie leci na hoście. Worker odpala każdy test przez `isolation/iso.sh` (Docker: bez sieci, limit RAM/CPU, timeout w kontenerze).

## Wymagania

- Python 3.12+
- Docker (Desktop + integracja WSL 2, albo zwykły Linux)
- Na Windowsie: WSL 2 — worker woła `iso.sh` przez `wsl`

Przed pierwszym jobem dociągnij obraz sędziego (worker robi to też przy starcie):

```powershell
python isolation/pull_images.py
```

## Uruchomienie

Dwa procesy: API i worker.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

W drugim terminalu (to samo venv):

```powershell
python scripts/worker.py
```

Wejdź na: http://127.0.0.1:8000/health

Dokumentacja API: http://127.0.0.1:8000/docs

Frontend (statyczny): pliki w `frontend/`.

Bez Dockera / WSL worker oznaczy zgłoszenie jako `RE` i napisze, że izolacji nie ma.

## Foldery

- `app/main.py` — API
- `app/db.py` — SQLite
- `app/models.py` — zadania, testy, zgłoszenia
- `scripts/worker.py` — kolejka zgłoszeń, woła `iso.sh`
- `isolation/pull_images.py` — dociąga obrazy Dockera przed pierwszym jobem
- `isolation/iso.sh` — sandbox Dockera
- `frontend/` — strony HTML

