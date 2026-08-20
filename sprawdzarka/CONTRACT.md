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

Z kluczem. Pełny pakiet do sędziego. Ten sam `submission_id` przy otwartym jobie (queued/leased) → ten sam job, bez duplikatu.

Wejście:

```json
{
  "submission_id": 42,
  "language": "python",
  "code": "print(1)",
  "time_limit_ms": 1000,
  "memory_limit_mb": 256,
  "checker": "exact",
  "checker_code": "",
  "tests": [
    {
      "id": 1,
      "input": "1 2\n",
      "output": "3\n",
      "position": 0,
      "group": "0",
      "max_score": 0
    }
  ]
}
```

`id` w teście to `test.id` z backendu — wraca jako `test_id` w callbacku. Ukryte testy są w tablicy (pełne I/O). Pola `hidden` nie ma.

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
