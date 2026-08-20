# Kontrakty — trzy aplikacje

Umowa, nie kod. Żywe endpointy: pliki w folderach.

| proces | port | plik |
|---|---|---|
| frontend (Vite/React/TS) | :3000 | [frontend/CONTRACT.md](frontend/CONTRACT.md) |
| backend (FastAPI, konta + zgłoszenia) | :8000 | [backend/CONTRACT.md](backend/CONTRACT.md) |
| sprawdzarka (HTTP → OIOIOI) | :8002, OIOIOI :8001 | [sprawdzarka/CONTRACT.md](sprawdzarka/CONTRACT.md) |

Przeglądarka → frontend → backend → sprawdzarka → OIOIOI. Wynik wraca **callbackiem** na backend. Język: **C++**. Isolation zostaje w repo, poza tą ścieżką.
