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
      "title": "Watermelon",
      "difficulty": 800,
      "tags": ["math", "brute force"],
      "source": "codeforces"
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
  "title": "Watermelon",
  "statement": "Opis zadania...",
  "difficulty": 800,
  "tags": ["math"],
  "source": "codeforces",
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
  "message": null
}
```

`status`: `queued` (w kolejce) | `running` (leci) | `done` (koniec)

`verdict` (tylko gdy `done`):
- `OK` — dobrze
- `WA` — zły wynik
- `TLE` — za wolno
- `MLE` — za dużo RAM
- `RE` — wywaliło się
- `CE` — nie skompilowało się

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
  "finished_last_minute": 40,
  "workers": 4
}
```
