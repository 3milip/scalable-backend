# OIOIOI

Gotowy stack SIO2 z obrazu GHCR. Źródła oioioi nie są w tym repo.

Port na hoście: **8001** (w kontenerze web słucha na 8000).

Wymaga: Docker Desktop + WSL 2.

## Setup

Z katalogu `oioioi/`. Compose sam czyta `.env`, jeśli go zrobisz.

```powershell
Copy-Item .env.example .env
docker compose pull
```

Bez `.env` i tak wstaje: tag `master`, strefa `Europe/Warsaw`.

Env:

- `OIOIOI_VERSION` = tag obrazu `ghcr.io/sio2project/oioioi` (domyślnie `master`)
- `OIOIOI_TIMEZONE` = domyślnie `Europe/Warsaw`

## Uruchomienie

```powershell
Set-Location oioioi
docker compose up
```

Pierwszy raz ściąga obraz + Postgres + RabbitMQ — to trwa.

Obraz deployment **nie** odpala `migrate` i bez `OIOIOI_SERVER_MODE` nic nie słucha na 8000 (port hosta 8001). Compose w tym repo ustawia `uwsgi-http`. Po pierwszym `up`:

```powershell
docker compose exec web ./manage.py migrate
docker compose restart web
```

Smoke C++ (contest `demo`, zadanie `sum`): paczka w `packages/sum/` (zip z katalogami `in/` i `out/` — sam zip z samymi plikami SIO2 odrzuca). Submit API zwraca id; po ocenie status bywa **`INI_OK` z `score: 100`** (to koniec, nie półmetek).

UI: http://127.0.0.1:8001/

Deployment compose SIO2 nie ładuje `admin/admin`. Jeśli nie ma loginu:

```powershell
docker compose exec web python manage.py createsuperuser
```

Stop: `Ctrl+C` albo `docker compose down`. Baza zostaje w volume. Kasowanie danych: `docker compose down -v`.
