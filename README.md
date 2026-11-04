# WorthRot

WorthRot helps people decide whether a video is worth watching for a specific
question. This repository is a runnable starter scaffold; video analysis is not
implemented yet.

## Requirements

- Python 3.10+
- Node.js 20.19+ and npm

## Run locally

Install the backend dependencies and start Flask:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
$env:PORT = "5000"
python main.py
```

In another terminal, install frontend dependencies and start Vite:

```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL printed in the terminal. Its `/health` and `/analyze`
requests are proxied to Flask. The analyze endpoint intentionally returns
`501 Not Implemented` until the analysis flow is added.

To serve the built frontend through Flask, build it first:

```powershell
cd frontend
npm run build
cd ..
$env:PORT = "5000"
python main.py
```

Flask binds to `0.0.0.0` and reads its port from `PORT` (default `5000`).

## Tests

```powershell
python -m pytest -q
```

## Project layout

- `app.py`, `main.py` — Flask application and server entry point
- `backend/routes/` — health and analysis API placeholders
- `frontend/` — React application built with Vite
- `tests/` — backend endpoint tests
- `docs/architecture.md` — current scaffold boundaries
