# Architecture

WorthRot is scaffolded as a Flask API with a React/Vite frontend. Flask serves
the production frontend from `frontend/dist` after it has been built. During
local development, Vite serves the UI and proxies API requests to Flask.

## Current endpoints

- `GET /health` returns `{"status": "ok"}`.
- `POST /analyze` returns a JSON `501 Not Implemented` message. It does not
  produce a verdict or evidence.

## Current boundaries

The UI collects a question and a YouTube URL and calls the placeholder analyze
endpoint. Transcript retrieval, analysis, evidence verification, and verdict
generation are not implemented in this scaffold. Add these behind backend
services and preserve the product's evidence and no-guessing rules when
implementing them.
