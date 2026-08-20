# Frontend

Statyczny HTML. Gada wyłącznie z backendem (`API_BASE` w `config.js`).

Port: **3000**.

## Uruchomienie

```powershell
Set-Location frontend
python -m http.server 3000
```

Wejdź na http://127.0.0.1:3000/

Domyślnie `config.js` ustawia `window.API_BASE = "http://127.0.0.1:8000"`. Backend musi mieć CORS (ma `allow_origins=*`).
