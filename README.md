# scalable-backend

Backend aplikacji do zadań programowania konkursowego.

## Uruchomienie

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Wejdź na: http://127.0.0.1:8000/health

Dokumentacja API (zrobi ją FastAPI sam): http://127.0.0.1:8000/docs

## Foldery

- `app/main.py` — start aplikacji
- `app/db.py` — połączenie z SQLite
- `app/models.py` — tabele (jeszcze puste)
