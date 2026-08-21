# Backend — publiczne API

Port: **8000**. Frontend woła tylko te endpointy. Sprawdzarka woła wyłącznie `POST /internal/results`.

Env: `SPRAWDZARKA_URL` (domyślnie `http://127.0.0.1:8002`), `SERVICE_KEY` (domyślnie `dev-service-key`), `DATABASE_URL` (domyślnie `sqlite:///./data/app.db`).

## GET /health

```json
{ "status": "ok" }
```

## GET /problems

Query: `limit` (domyślnie 20), `offset`, `tag`, `difficulty`.

```json
{
  "total": 120,
  "items": [
    {
      "id": 1,
      "title": "Suma dwóch liczb",
      "difficulty": 800,
      "tags": ["math", "implementation"],
      "source": "local"
    }
  ]
}
```

## GET /problems/{id}

Treść zadania. 404 gdy brak.

## POST /submissions

```json
{ "problem_id": 1, "language": "cpp", "code": "#include <iostream>\nint main() { int a, b; std::cin >> a >> b; std::cout << a + b << \"\\n\"; }\n" }
```

`language` tylko `"cpp"`. Inna wartość → 422.

Zapisuje zgłoszenie i pcha job na sprawdzarkę (`POST {SPRAWDZARKA_URL}/jobs` z `X-Service-Key`). Jeśli POST nie przejdzie — status `failed`, wiadomość `sprawdzarka nieosiągalna`.

```json
{ "id": 42, "status": "queued" }
```

## GET /submissions

Lista zgłoszeń (`limit`, `offset`).

## GET /submissions/{id}

Wynik. Ukryty test: `verdict` + `group`, bez `input`/`output`. Przykład może pokazać I/O.

`status`: `queued` | `running` | `done` | `failed`

`verdict` (gdy `done`): `OK` `WA` `TLE` `MLE` `RE` `CE` `SI`

## GET /stats

`queued` / `running` / `failed` / `finished_last_minute` z bazy zgłoszeń. `workers` z `GET {SPRAWDZARKA_URL}/stats`; timeout/błąd → `0`.

## POST /internal/results

Tylko sprawdzarka. Nagłówek `X-Service-Key`. Kontrakt body: `sprawdzarka/CONTRACT.md`.

- nieznane `submission_id` → 404
- już `done`/`failed` + `running` albo drugi finał → 200, bez zmiany
- `running` → status running
- `done` → zapis werdyktu i wierszy testów (`test_id` = `tests.id`)
- `failed` → status failed
