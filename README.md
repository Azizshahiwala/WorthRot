# WorthRot

WorthRot helps people decide whether a video answers a specific question. It
returns a verdict, short timestamped facts verified against the transcript, and
any missing topics, with a question-level gap check. Compare ranks videos and
summarizes agreement using their verified facts.

## Requirements

- Python 3.10+
- Node.js 20.19+ and npm

## Run locally

Install the backend dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

For live analysis, add your Bazaarlink API key to the root `.env` file:

```env
BAZAARLINK_API_KEY=your-bazaarlink-api-key
GEMINI_API_KEY=your-gemini-api-key
ELEVEN_LABS_API=your-elevenlabs-api-key
LLM_BASE_URL=https://api.bazaarlink.ai/v1
MODEL_NAME=qwen/qwen3.7-flash:free
```

The app loads `.env` for local development. Keep the key out of source control;
`.env` is ignored by Git. `.env.example` lists all supported pipeline settings.
`GEMINI_API_KEY` enables speech-to-text for MP3 uploads and MP4 files without
embedded subtitles. Bazaarlink remains responsible for analyzing transcripts
and frame analysis. If Gemini returns HTTP 429, `ELEVEN_LABS_API` enables the
ElevenLabs transcription fallback. Completed Other and Compare analyses are
saved to History as result summaries only; uploaded files and transcripts are
not saved.
For hosted deployments, configure `BAZAARLINK_API_KEY`, `LLM_BASE_URL`, and
`MODEL_NAME` as
environment variables in the hosting dashboard instead of uploading `.env`.
Local SQLite cache data defaults to `src/backend/data`; hosted deployments
should provide a persistent `DATA_DIR`.

If analysis reports a model-provider error, check the backend response message:
it distinguishes rejected keys, model access or name problems, usage limits,
and temporary provider outages. Confirm the key and model are configured in the
same environment that runs Flask.

Successful verdicts are also kept in this browser's History tab using
`localStorage` (up to 50 entries). History is not synced or sent to the server.
If browser storage is blocked, analysis still works for the current session.

Install frontend dependencies:

```powershell
cd frontend
npm install
```

From the repository root, run `start-worthrot.bat`. It opens separate terminal
windows for Flask and Vite. Open the Vite URL printed in its terminal; its
`/health` and `/analyze` requests are proxied to Flask. YouTube captions may be
unavailable from some hosted networks; paste a timestamped transcript as the
fallback.

To start the servers manually, run `python main.py` in one terminal and
`npm run dev` from `frontend` in another.

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

Frontend unit tests:

```powershell
cd frontend
npm test
```

The optional live Bazaarlink test sends a short sample transcript and prints
the model's parsed and verified response. It does not load `.env`; provide
`BAZAARLINK_API_KEY` in the process environment, then opt in explicitly:

```powershell
$env:RUN_LIVE_LLM_TESTS = "1"
python -m pytest tests/test_bazaarlink_live.py -q -s
```

The test uses `MODEL_NAME` from the process environment, or
`qwen/qwen3.7-flash:free` if unset. It makes a real API request; check
Bazaarlink's pricing and limits before running it.

## Project layout

- `app.py`, `main.py` — Flask application and server entry point
- `backend/routes/` — health and analysis API
- `backend/services/` — transcript cleaning, retrieval, verification, and
  verdict generation
- `frontend/` — React application built with Vite
- `tests/` — offline backend pipeline and endpoint tests
- `docs/architecture.md` — pipeline, API contract, and sequence diagram
