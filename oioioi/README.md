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

UI: http://127.0.0.1:8001/

Deployment compose SIO2 nie ładuje `admin/admin`. Jeśli nie ma loginu:

```powershell
docker compose exec web python manage.py createsuperuser
```

Stop: `Ctrl+C` albo `docker compose down`. Baza zostaje w volume. Kasowanie danych: `docker compose down -v`.
