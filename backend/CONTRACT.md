# Backend — kontrakt HTTP

Aplikacja: FastAPI. Proces na **http://127.0.0.1:8000**.

Źródło prawdy o: kontach, sesjach, liście zadań (JSON), rekordach zgłoszeń (status, punkty).
Nie gada z OIOIOI. Sędziego woła przez **sprawdzarkę**.

```
przeglądarka → frontend :3000 → backend :8000 → sprawdzarka :8002 → OIOIOI :8001
                                      ↑ callback ─────────┘
```

Env:

```
SERVICE_KEY=...
SPRAWDZARKA_URL=http://127.0.0.1:8002
PUBLIC_CALLBACK_BASE=http://127.0.0.1:8000
```

`SERVICE_KEY` ten sam co w sprawdzarce. Nagłówek serwisowy: `X-Service-Key`.

---

## Publiczne (przeglądarka, Bearer)

### GET /health

```json
{ "status": "ok" }
```

### POST /auth/register  POST /auth/login

Wejście: `{ "username": "ala", "password": "tajne1" }`
Wyjście: `{ "token": "...", "username": "ala" }`

Login: 3–32 znaki `[A-Za-z0-9_]`. Hasło min. 6. **Nie** zakłada konta w OIOIOI.

### GET /auth/me

Wyjście: `{ "username": "ala" }`

### GET /problems

Query: `limit`, `offset`, `tag`, `difficulty`.
Wyjście: `{ "total": N, "items": [{ "id", "title", "difficulty", "tags", "source" }] }`

### GET /problems/{id}

Jak lista + `statement`, `time_limit_ms`, `memory_limit_mb`, `solution`.
404 gdy brak.

### POST /submissions

Wymaga logowania. Tylko `language: "cpp"` (inny → 400).

```json
{ "problem_id": 1, "language": "cpp", "code": "#include <iostream>\\n..." }
```

Backend: zapisuje wiersz `queued`, woła sprawdzarkę `POST /jobs`, zapamiętuje `judge_job_id`.
Wyjście od razu: `{ "id": 42, "status": "queued" }`
Sprawdzarka martwa → 502, rekord `failed`.

### GET /submissions  GET /submissions/{id}

Rekord z bazy backendu (callback już nadpisał wynik).
Lista: swoje zgłoszenia, `problem_title`.
Szczegół: + `tests[]` (gdy callback je przysłał).

`status`: `queued` | `running` | `done` | `failed`
`verdict` (przy `done`): `OK` `WA` `TLE` `MLE` `RE` `CE` `SI`

### GET /stats

Kolejka **naszych** rekordów, nie workerów isolation.

```json
{ "queued": 3, "running": 2, "failed": 1, "finished_last_minute": 40, "workers": 0 }
```

`workers` na razie 0 (sędzia jest poza isolation).

---

## Wewnętrzne (tylko sprawdzarka, X-Service-Key)

### POST /internal/submissions/{id}/result

Callback po ocenie. Idempotentny: ten sam wynik drugi raz = 200, bez zmiany.

```json
{
  "job_id": "j-1",
  "status": "done",
  "verdict": "OK",
  "score": 3,
  "max_score": 3,
  "time_ms": 15,
  "memory_kb": 4200,
  "message": null,
  "tests": [
    {
      "position": 0,
      "group": "0",
      "hidden": false,
      "verdict": "OK",
      "score": 0,
      "max_score": 0,
      "time_ms": 12,
      "memory_kb": 700,
      "message": null,
      "input": "1 2\\n",
      "output": "3\\n"
    }
  ]
}
```

Brak klucza / zły klucz → 401. Nie ma zgłoszenia → 404.
`status` tylko `done` albo `failed`.

---

## Wychodzące (backend → sprawdzarka)

`POST {SPRAWDZARKA_URL}/jobs` z `X-Service-Key`. Ciało: `sprawdzarka/CONTRACT.md`.

`callback_url` = `{PUBLIC_CALLBACK_BASE}/internal/submissions/{id}/result`

Push zadań (osobna komenda, nie request z frontu):
`POST {SPRAWDZARKA_URL}/problems/sync` — JSON zadań / zip-y SINOL.

---

## Zadania

Źródło: `data/local_problems.json` (przy backendzie).
`id` w API = id w bazie backendu. Na sędziego idzie `short_name` (`local-01` → `loca`).
