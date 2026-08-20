# Sprawdzarka — kontrakt HTTP

Aplikacja: cienki serwer HTTP na **http://127.0.0.1:8002**.
W środku: oficjalny OIOIOI (Docker) na **http://127.0.0.1:8001**, contest `local`.

Dla backendu to czarna skrzynka: kod IN → werdykt OUT. **Nie** zna haseł zawodników. Ranking OIOIOI nie jest rankingiem portalu — zgłoszenia idą na **konto serwisowe**.

```
backend :8000  --POST /jobs-->  sprawdzarka :8002  --submit-->  OIOIOI :8001
backend :8000  <--POST result--  sprawdzarka (poll OIOIOI, potem callback)
```

Env:

```
SERVICE_KEY=...
OIOIOI_URL=http://127.0.0.1:8001
OIOIOI_CONTEST_ID=local
OIOIOI_SERVICE_TOKEN=...
```

OIOIOI stoi compose’em w tym folderze (`docker compose up`, web :8001). Sprawdzarka to **osobny proces na hoście**: przyjmuje job, wysyła do OIOIOI, **polluje** status, sama woła backend. Kontener OIOIOI nie musi widzieć Windowsa.

Język na wejściu: tylko `cpp`. Inny → 400.

---

## Publiczne dla backendu (X-Service-Key)

### GET /health

```json
{ "status": "ok", "oioioi": "ok" }
```

`oioioi` = `ok` | `down`. 200 nawet gdy OIOIOI down, żeby dało się odróżnić.

### POST /jobs

```json
{
  "backend_submission_id": 42,
  "callback_url": "http://127.0.0.1:8000/internal/submissions/42/result",
  "problem_short_name": "loca",
  "language": "cpp",
  "code": "#include <iostream>\\nint main() { ... }\\n"
}
```

Wyjście: `{ "job_id": "j-1", "status": "queued" }`

Sprawdzarka: submit do OIOIOI jako konto serwisowe, `job` w pamięci/SQLite (`queued` → `running` → `done`/`failed`).

### GET /jobs/{job_id}

Podgląd (debug). Ten sam kształt co callback, plus `backend_submission_id`.

### POST /problems/sync

Wejście: lista zadań jak w `local_problems.json` **albo** multipart zip-ów SINOL.
Wyjście: `{ "upserted": ["loca", "locb"], "errors": [] }`

Tworzy/aktualizuje paczki w contestcie `local`. Ustawia rundę tak, żeby wyniki były widoczne (inaczej API OIOIOI chowa score i zostaje wieczne `INI_OK`).

---

## Wychodzące (sprawdzarka → backend)

Gdy OIOIOI skończy (albo 3× padnie poll):

`POST {callback_url}`  
nagłówek `X-Service-Key`  
ciało = `backend/CONTRACT.md` → `POST /internal/submissions/{id}/result`

Mapowanie statusu OIOIOI **tutaj**, nie w backendzie:

| OIOIOI | my |
|---|---|
| `?` `PENDING` | jeszcze nie callback (`running`) |
| `INI_OK` bez score | czekaj dalej |
| `INI_ERR` | `done` / `WA` |
| `INI_OK` + score, score ≥ max | `done` / `OK` |
| `INI_OK` + score, score < max | `done` / `WA` |
| `OK` `WA` `TLE` `MLE` `RE` `CE` | `done` / ten werdykt |
| `ERR` / wyjątek | `failed` |

Callback raz na job. Gdy backend 5xx — retry kilka razy.

---

## Czego tu nie ma

- Logowania zawodnika
- Treści zadań dla przeglądarki (to backend)
- isolation/iso.sh (zostaje w repo poza tą aplikacją)
