# Frontend — kontrakt klienta

Aplikacja: **Vite + React + TypeScript**. Proces na **http://127.0.0.1:3000**.

To nie jest serwer API. Front **woła wyłącznie backend** (`VITE_API_URL`, domyślnie `http://127.0.0.1:8000`). Nie woła sprawdzarki ani OIOIOI.

## Uruchomienie (docelowe)

```powershell
Set-Location frontend
npm install
npm run dev
```

## Auth

Po `POST /auth/register` albo `POST /auth/login` zapisuje `token` i `username`.
Każdy request oprócz logowania/rejestracji: `Authorization: Bearer <token>`.
401 → strona logowania.

## Język

Zgłoszenia tylko **C++** (`language: "cpp"`). W UI nie ma Pythona.

## Ekrany

| trasa | woła |
|---|---|
| `/login` | `POST /auth/register`, `POST /auth/login` |
| `/problems` | `GET /problems` |
| `/problems/:id` | `GET /problems/:id`, `POST /submissions` |
| `/submissions` | `GET /submissions` (poll ~2 s gdy są `queued`/`running`) |
| `/submissions/:id` | `GET /submissions/:id` (poll aż `done`/`failed`) |
| `/stats` | `GET /stats` |

Kształt JSON: `backend/CONTRACT.md` (część publiczna). Front nie zgaduje pól OIOIOI (`INI_OK` itd.) — dostaje `queued` / `running` / `done` / `failed` i werdykt `OK`/`WA`/…

## CORS

Backend puszcza origin `http://127.0.0.1:3000` (i `http://localhost:3000`).
