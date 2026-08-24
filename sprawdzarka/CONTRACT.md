# Sprawdzarka — kontrakt HTTP

Port: **8002**. Ruch od backendu. Nagłówek `X-Service-Key` (ten sam `SERVICE_KEY` co backend). Brak/zły klucz → 401. Wyjątek: `GET /health`.

Env: `BACKEND_URL` (domyślnie `http://127.0.0.1:8000`), `SERVICE_KEY` (domyślnie `dev-service-key`), `DATABASE_URL` (domyślnie `sqlite:///./data/jobs.db`).

## GET /health

Bez klucza.

```json
{ "status": "ok" }
```

## GET /stats

Z kluczem.

```json
{ "workers": 2 }
```

`workers` — ile procesów workera dało heartbeat w ostatniej minucie (lease 60 s).

## POST /jobs

Z kluczem. Worker pcha kod do OIOIOI (`short_name` + `main.cpp`). Ten sam `submission_id` przy otwartym jobie (queued/leased) → ten sam job, bez duplikatu. `language` tylko `"cpp"`.

Wejście:

```json
{
  "submission_id": 42,
  "language": "cpp",
  "code": "#include <iostream>\nint main() { int a, b; std::cin >> a >> b; std::cout << a + b << \"\\n\"; }\n",
  "short_name": "sum"
}
```

`short_name` = id zadania w contestcie OIOIOI (`Problem.external_id`). Live **nie** wysyła `tests` / `checker` / limitów z JSON-a — ocenia paczka SIO2. Stare pola API jeszcze przyjmuje (isolate w testach). Callback v1: `tests: []`.

Po udanym submitcie worker pollowa tylko `GET /api/c/{contest}/submission_report/{id}/` (404/5xx → retry, nie `failed`). Karty gdy `complete: true` (raport NORMAL albo CE). `INI_OK` = przykłady, nie koniec. Werdykt/score/czas/RAM z testów punktowanych (RAM 0 pomijane). Submit 404 (nie ma zadania) nadal kończy joba jako `failed`.

`id` w teście to `test.id` z backendu — wraca jako `test_id` w callbacku, gdy sędzia lokalny kiedyś zwracał wiersze. Pola `hidden` nie ma.

Odpowiedź `201`:

```json
{ "id": 7, "submission_id": 42, "status": "queued" }
```

`id` = job w bazie sprawdzarki.

## Callback do backendu

Sprawdzarka woła `POST {BACKEND_URL}/internal/results` z `X-Service-Key`.

Start (po claim):

```json
{ "submission_id": 42, "status": "running" }
```

Koniec (w tym CE):

```json
{
  "submission_id": 42,
  "status": "done",
  "verdict": "OK",
  "time_ms": 15,
  "memory_kb": 4200,
  "message": null,
  "score": 3,
  "max_score": 3,
  "tests": [
    {
      "test_id": 1,
      "verdict": "OK",
      "time_ms": 12,
      "memory_kb": 7000,
      "score": 0,
      "max_score": 0,
      "message": null
    }
  ]
}
```

Po 3 wygasłych lease’ach:

```json
{ "submission_id": 42, "status": "failed", "message": "lease wygasl, limit prob" }
```

Retry sędziego (lease/heartbeat/3 próby) jest wewnątrz sprawdzarki. Worker: osobny proces `python -m sprawdzarka.worker`.
