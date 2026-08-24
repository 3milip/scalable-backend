# scalable-backend

Trzy osobne aplikacje, które gadają ze sobą po HTTP. Nie współdzielą bazy ani importów Pythona.

| | port | start |
|---|---|---|
| [frontend](frontend/README.md) | :3000 | `cd frontend; python -m http.server 3000` |
| [backend](backend/README.md) | :8000 | `cd backend; uvicorn app.main:app --port 8000` |
| [sprawdzarka](sprawdzarka/README.md) | :8002 | API: `cd sprawdzarka; uvicorn sprawdzarka.main:app --port 8002` · worker: `python -m sprawdzarka.worker` |
| [oioioi](oioioi/README.md) | :8001 | `cd oioioi; docker compose up` |

Przeglądarka → frontend → backend → sprawdzarka (adapter OIOIOI). Wynik wraca callbackiem na backend. Język zgłoszeń: **C++** (`language: "cpp"`). Zadanie `sum` ma paczkę w contestcie `demo` na `:8001`.

Kontrakty: [backend/CONTRACT.md](backend/CONTRACT.md), [sprawdzarka/CONTRACT.md](sprawdzarka/CONTRACT.md).

## Werdykty (na karcie zgłoszenia)

Tylko gdy status jest `done`. `failed` to nie werdykt — ocena w ogóle nie doszła (np. brak zadania w OIOIOI).

| kod | znaczenie |
|---|---|
| **OK** | program dał poprawny wynik |
| **WA** | zły wynik (Wrong Answer) |
| **TLE** | za długo (Time Limit Exceeded) |
| **MLE** | za dużo RAM (Memory Limit Exceeded) |
| **RE** | wywalił się w trakcie (Runtime Error) |
| **CE** | nie skompilował się (Compilation Error) |
| **SI** | błąd sędziego / nieznany status z OIOIOI |

RAM i czas na karcie to pomiar z OIOIOI (szczyt z testów), nie limit zadania.

## Setup (raz)

Wymagane: Python 3.12+, Docker Desktop (WSL 2) dla stacku OIOIOI (`oioioi/`). Worker sprawdzarki nie woła już lokalnego `g++`.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
pip install -r sprawdzarka/requirements.txt
Set-Location backend; python scripts/import_problems.py; Set-Location ..
Copy-Item sprawdzarka\.env.example sprawdzarka\.env
```

`SERVICE_KEY` ten sam w backendzie i sprawdzarce (domyślnie `dev-service-key`).

OIOIOI pierwszy raz — z `oioioi/`, w osobnym oknie zostaw `docker compose up`:

```powershell
Set-Location oioioi
docker compose pull
docker compose up
```

Jak wstanie (pierwszy raz długo), w drugim oknie:

```powershell
Set-Location oioioi
docker compose exec web ./manage.py migrate
docker compose restart web
docker compose exec web python manage.py createsuperuser
```

`restart web` ładuje apkę `adapter_report` (czas/RAM na kartach). Przy zmianie volume: `docker compose up` od nowa w katalogu `oioioi/`.

UI: http://127.0.0.1:8001/ — załóż contest `demo`, wgraj zip z `oioioi/packages/sum/` (musi mieć katalogi `in/` i `out/`). Konto **zwykłe** (np. `adapter`, nie superuser), potem token:

```powershell
docker compose exec web python manage.py drf_create_token adapter
```

Wklej do `sprawdzarka/.env` jako `OIOIOI_TOKEN=...` (`OIOIOI_URL` i `OIOIOI_CONTEST_ID=demo` już są w example).

## Ściąga — odpal wszystko

Z katalogu repo. Docker Desktop włączony. W **każdym** oknie Pythona najpierw:

```powershell
.\.venv\Scripts\Activate.ps1
```

Pięć okien, każde z korzenia repo:

```powershell
Set-Location oioioi; docker compose up
```

```powershell
Set-Location frontend; python -m http.server 3000
```

```powershell
Set-Location backend; uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```powershell
Set-Location sprawdzarka; uvicorn sprawdzarka.main:app --reload --host 127.0.0.1 --port 8002
```

```powershell
Set-Location sprawdzarka; python -m sprawdzarka.worker
```

| co | url |
|---|---|
| strona | http://127.0.0.1:3000/ |
| backend | http://127.0.0.1:8000/health · docs http://127.0.0.1:8000/docs |
| sprawdzarka | http://127.0.0.1:8002/health |
| OIOIOI | http://127.0.0.1:8001/ |

Bez OIOIOI albo bez `OIOIOI_TOKEN` worker nie wstanie. Bez workera joby wiszą w `queued`.

Stop: `Ctrl+C` w oknach. OIOIOI: `docker compose down` (baza zostaje; kasowanie: `docker compose down -v`).

## Testy

```powershell
Set-Location backend; python -m unittest discover -s tests -v
Set-Location ..\sprawdzarka; python -m unittest discover -s tests -v
```

Lokalny sędzia (`iso.sh`) jest tylko pod testy — obrazy: `Set-Location sprawdzarka; python -m sprawdzarka.pull_images`.
