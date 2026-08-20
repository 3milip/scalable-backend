# scalable-backend

Sędzia zadań programistycznych: kolejka jobów, ocena w Dockerze, punkty grupami.

Kod zawodnika nie leci na hoście. Każdy test (i compile, i custom checker) idzie przez `isolation/iso.sh`.

## Odpalenie (skopiuj)

Wymagane: Python 3.12+, Docker Desktop włączony (WSL 2). Polecenia odpalaj w katalogu repo.

**1. Raz — setup** (nowe okno PowerShell):

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python isolation/pull_images.py
python scripts/import_problems.py
```

Import wczytuje zadania do bazy. Odpalaj go tylko na start albo gdy chcesz **wyzerować** zgłoszenia.

**2. Terminal 1 — strona i API** (zostaw włączone):

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**3. Terminal 2 — worker** (bez tego zgłoszenia wiszą w `queued`):

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python isolation/worker.py
```

Potem wejdź na: http://127.0.0.1:8000/

- zdrowie: http://127.0.0.1:8000/health
- API: http://127.0.0.1:8000/docs

Zatrzymanie: `Ctrl+C` w obu oknach. Job w trakcie wraca do kolejki i **nie spala** próby.

Bez Dockera / WSL worker się nie uruchomi.

## OIOIOI (osobny stack)

Nie zastępuje uvicorn ani `isolation/worker.py`. To oficjalny compose SIO2: strona contestów na **:8001**, wasz sędzia zostaje na **:8000**. Zgłoszenia nie przechodzą między stosami.

Obraz: `ghcr.io/sio2project/oioioi` ([GHCR](https://github.com/sio2project/oioioi/pkgs/container/oioioi) — to jest oficjalny obraz; tag z Docker Huba z ich compose nie istnieje). Compose: `oioioi/docker-compose.yml`. Lokalnie tylko port **8001**, żeby nie zająć `:8000`.

**Raz — opcjonalnie** pin tagu (domyślnie `master`):

```powershell
Copy-Item oioioi\.env.example oioioi\.env
```

**Start** (Docker Desktop włączony):

```powershell
Set-Location oioioi
docker compose up
```

Więcej workerów OIOIOI:

```powershell
docker compose up --scale worker=3
```

Potem: http://127.0.0.1:8001/ — konto `admin` / `admin`. Zmień hasło od razu.

Stop: `Ctrl+C` albo `docker compose down`. Postgres i testy OIOIOI siedzą w wolumenach Dockera, nie w `data/app.db`.

## Zgłoszenie ≠ job

- **Zgłoszenie** — to, co widać na stronie (kod, werdykt, punkty, tabela testów).
- **Job** — jednostka w kolejce (`jobs`). Na razie jeden rodzaj: `judge` (compile + wszystkie testy).

`POST /submissions` zapisuje zgłoszenie i robi `enqueue`. Worker robi `claim` na **jobie**, nie na wierszu zgłoszenia.

Kilka workerów: jeden job bierze jeden proces (atomowy lease, 60 s, heartbeat co 10 s). Po 3 wygasłych lease’ach job i zgłoszenie idą do `failed`.

## Werdykty

- `OK` `WA` `TLE` `MLE` `RE` `CE` — ocena kodu
- `SI` — padł checker / sędzia, nie wina zawodnika
- **`failed`** — worker trzy razy umarł w trakcie; to **nie jest WA**

Punkty jak OIOIOI: testy w **grupach**. Grupa = minimum (jeden WA zeruje całą paczkę). Zadanie = suma grup. Maks to suma grup, nie suma testów. Przykłady (`max_score = 0`) się nie liczą. Odpalane są wszystkie testy (poza CE na compile).

## Import zadań

```powershell
python scripts/import_problems.py
```

Kasuje bazę i wczytuje `data/local_problems.json`.

v1: przykłady → grupa `"0"`, 0 pkt; każdy ukryty test → **własna** grupa (numer pozycji), 1 pkt, więc pełny OK = pełne punkty. W JSON ta sama `group` na kilku testach = paczka OI (wszystko albo nic). Można nadpisać `group` / `max_score`.

Checker (pole zadania, default `exact`):

- `exact` — porównanie znormalizowanego tekstu
- `tokens` — sekwencja słów, spacje nieważne
- `float` — tokeny, liczby z eps `1e-6`
- `custom` — skrypt w Dockerze (`checker_code`); exit 0 = OK, 1 lub 2 = WA, reszta = SI

## Testy

```powershell
python -m unittest tests.test_queue tests.test_results tests.test_scoring tests.test_judge tests.test_checker -v
```

## Druga maszyna

Nie kopiuj `data/app.db` przez sieć. Kolejka jest dziś SQLite na jednym komputerze. Wspólny Postgres albo Redis to osobny silnik za tym samym portem (`claim` / `ack` / `nack`) — nie jest w tym README.

`iso.sh` i tak zostaje lokalny: każda maszyna ma własną pulę Dockera.

## Foldery

- `app/main.py` — API
- `isolation/` — kolejka, izolacja, sędzia, checker, worker (łatwe do wyjęcia)
  - `queue.py` — enqueue / claim / heartbeat / ack / nack / fail
  - `isolate.py` + `iso.sh` — sandbox Dockera
  - `pull_images.py` — obraz sędziego
  - `judge.py` — compile, przykłady, testy, punkty
  - `checker.py` — exact / tokens / float / custom
  - `worker.py` — pętla claim → judge → ack
- `scripts/worker.py` — skrót do `isolation/worker.py`
- `frontend/` — HTML (serwisowane z `/`)
- `oioioi/` — oficjalny Docker OIOIOI (web :8001, Postgres, RabbitMQ, worker)
