# Kontrakty endpointów

To nie jest jeszcze działający kod. To umowa: jakie adresy będą i co zwracają.

## GET /health

Cel: sprawdzić, czy serwer żyje.

Wejście: nic.

Wyjście:
```json
{ "status": "ok" }
```

---

## GET /problems

Cel: lista zadań.

Wejście (w adresie, opcjonalne):
- `limit` — ile zadań (domyślnie 20)
- `offset` — od którego (domyślnie 0)
- `tag` — filtr, np. `dp`
- `difficulty` — filtr, np. `800`

Wyjście:
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

---

## GET /problems/{id}

Cel: jedno zadanie, ze treścią.

Wejście: `id` w adresie.

Wyjście:
```json
{
  "id": 1,
  "title": "Suma dwóch liczb",
  "statement": "Opis zadania...",
  "difficulty": 800,
  "tags": ["math"],
  "source": "local",
  "time_limit_ms": 1000,
  "memory_limit_mb": 256
}
```

Jak nie ma takiego id: błąd 404.

---

## POST /submissions

Cel: wyślij kod do sprawdzenia. Trafia do kolejki, nie czeka na wynik.

Wejście:
```json
{
  "problem_id": 1,
  "language": "python",
  "code": "print(1)"
}
```

Wyjście (od razu, status `queued`):
```json
{
  "id": 42,
  "status": "queued"
}
```

---

## GET /submissions/{id}

Cel: wynik sprawdzania.

Wejście: `id` w adresie.

Wyjście:
```json
{
  "id": 42,
  "problem_id": 1,
  "language": "python",
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
      "position": 0,
      "group": "0",
      "hidden": false,
      "verdict": "OK",
      "time_ms": 12,
      "memory_kb": 7000,
      "score": 0,
      "max_score": 0,
      "message": null,
      "input": "1 2\\n",
      "output": "3\\n"
    },
    {
      "test_id": 2,
      "position": 1,
      "group": "1",
      "hidden": true,
      "verdict": "OK",
      "score": 1,
      "max_score": 1,
      "input": null,
      "output": null
    }
  ]
}
```

`score` / `max_score` — punkty (przykłady mają `max_score` 0 i nie liczą się). Przy `running` tablica `tests` może być niepełna.

Ukryty test: `verdict` + `group`, bez `input`/`output`. Przykład może pokazać I/O.

`status`: `queued` (w kolejce) | `running` (leci) | `done` (koniec) | `failed` (worker nie dał rady)

`verdict` (tylko gdy `done`):
- `OK` — dobrze
- `WA` — zły wynik
- `TLE` — za wolno
- `MLE` — za dużo RAM
- `RE` — wywaliło się
- `CE` — nie skompilowało się
- `SI` — błąd sędziego/checkera, nie wina kodu

Jak nie ma takiego id: błąd 404.

---

## GET /stats

Cel: pokazać, czy system ogarnia dużo requestów naraz.

Wejście: nic.

Wyjście:
```json
{
  "queued": 3,
  "running": 2,
  "failed": 1,
  "finished_last_minute": 40,
  "workers": 2
}
```

`workers` — ile procesów workera dało znać w ostatniej minucie (heartbeat), nie stała.

`failed` — zgłoszenia, których worker nie dokończył 3 razy (dead letter), nie mylić z WA.
