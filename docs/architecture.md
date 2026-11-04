# Architecture

WorthRot uses a Flask API with a React/Vite frontend. Flask serves the
production frontend from `frontend/dist` after it has been built. Its catch-all
serves `index.html` for client-side routes such as `/compare`, while the
registered API routes remain higher priority. During local development, Vite
serves the UI and proxies API requests to Flask.

## Frontend structure

- `src/config/tabs.js` is the single list of navigation labels, routes, page
  elements, and availability.
- `src/main.jsx` composes `BrowserRouter`, `ThemeProvider`, `ToastProvider`,
  `AnalysisProvider`, and the layout in that order.
- `src/layout/` contains the shared navigation and route outlet.
- `src/contexts/` separates analysis, theme, and toast state. Each context
  provides a guarded custom hook and memoized actions/state.
- `src/components/ui/` contains the reusable design-system primitives;
  `src/components/youtube/` contains analyzer form and result components.
- `src/styles/` holds theme tokens, base styles, and component styles.
- `/compare`, `/instagram`, `/history`, and `/about` are navigation-ready
  placeholders. The YouTube analyzer is the only functional page.

## Current endpoints

- `GET /health` returns `{"status": "ok"}`.
- `POST /analyze` returns a JSON `501 Not Implemented` message. It does not
  produce a verdict or evidence.

## Current boundaries

The YouTube UI accepts a question and either a YouTube URL or pasted
transcript, then calls the existing placeholder analyze endpoint. Transcript
retrieval, analysis, evidence verification, and verdict generation are not
implemented in this scaffold. No verdict is fabricated when the endpoint
returns its current `501 Not Implemented` response. Implement analysis behind
backend services and preserve the product's evidence and no-guessing rules.
