# WorthRot Documentation

WorthRot checks whether a video covers a user's question. It returns a verdict,
verified timestamped facts, topics that are missing, and (when available) a
question-level gap check. Results are designed to be concise and evidence
based.

## Features

- **YouTube:** analyze a video using captions or a pasted timestamped
  transcript.
- **Multilingual analysis:** select captions across languages, keep quotes in
  their source language, and write results in the question language. Long
  cross-language analyses may translate the question for retrieval only.
- **Compare:** rank two or three YouTube videos for one question and optionally
  summarize agreement and disagreement from verified facts.
- **Other:** analyze one uploaded MP4 or MP3 using embedded subtitles, speech
  transcription, or sampled video frames.
- **Question gap checks:** show which parts of the question are covered,
  partially covered, or missing.
- **History:** keep up to 50 successful analysis summaries in browser storage.
- **Daily limits:** show per-feature request availability and protect provider
  capacity.

## How analysis works

For YouTube and transcript-based media, WorthRot prepares timestamped
transcript windows and ranks them locally against the question. The model
receives bounded context and returns candidate facts with internal source
quotes. The verifier checks each quote against the source window; unverified
facts are dropped. Code maps the verified evidence to a verdict.

When question and transcript languages differ, a long transcript may use a
small retrieval-only question translation. This translation is never treated
as evidence. A failed translation falls back to best-effort retrieval and is
reported in metadata. Language detection may be heuristic if the caption or
transcription provider does not supply a language code.

For Compare, each video is analyzed independently. The code ranker determines
the order; the optional agreement request sees verified facts only and cannot
alter the rank.

For MP4 uploads, processing prefers embedded subtitles, then speech
transcription, then sampled frames. MP3 uploads use speech transcription.
Frame-based facts must match timestamps of frames actually sent, and their
verdict is capped at `Skim`.

## Verdicts and evidence

| Verdict | Meaning |
|---|---|
| `Worth it` | The checked evidence substantially answers the question. |
| `Skim` | Some useful evidence answers part of the question. |
| `Rot` | Available evidence does not answer the question. |
| `Can't verify` | The source could not be checked reliably. |

`Worth it` and `Skim` require at least one verified timestamped fact. Results
are only as reliable as their captions, transcript, speech recognition, or
sampled frames. Check the original video when accuracy is important.

## Web API

All errors return JSON with a human-readable `message`.

### `POST /analyze`

```json
{
  "question": "How do I sharpen a knife?",
  "urls": ["https://youtu.be/abcdefghijk"]
}
```

You may provide a timestamped transcript instead of a URL:

```json
{
  "question": "How do I sharpen a knife?",
  "urls": [],
  "transcript": "[00:12] Hold the blade at a steady angle."
}
```

The successful response includes:

```json
{
  "verdict": "Skim",
  "facts": [
    {
      "text": "Hold the blade at a steady angle.",
      "timestamp": "00:12",
      "url": "https://youtu.be/abcdefghijk?t=10"
    }
  ],
  "missing": ["How often to sharpen"],
  "gap": {
    "covered": 1,
    "total": 2,
    "label": "Partly covered",
    "parts": [
      { "text": "Sharpening angle", "status": "covered" },
      { "text": "Maintenance", "status": "missing" }
    ]
  },
  "meta": {
    "video_id": "abcdefghijk",
    "cached": false,
    "tokens_in": 0,
    "tokens_out": 0,
    "questionLanguage": "en",
    "transcriptLanguage": "en",
    "transcriptOriginalLanguage": "en",
    "transcriptSource": "manual",
    "retrievalTranslationFailed": false
  }
}
```

The `gap` can be `null`. The internal quote used to verify a fact is not
returned. For a pasted transcript with no YouTube URL, fact URLs are empty.

### `POST /compare`

Accepts two or three distinct YouTube URLs:

```json
{
  "question": "What power supply does this device need?",
  "urls": [
    "https://youtu.be/abcdefghijk",
    "https://youtu.be/lmnopqrstuv"
  ]
}
```

The response includes the question language, ranked per-video results, a
nullable `best` video ID, optional agreement (`agree`, `disagree`,
`unanswered`), and aggregate token usage. A video's error is returned on that
row without failing other rows. `best` is set only when the top verdict is
`Worth it` or `Skim`.

### `POST /analyze-media`

Send multipart form data with `question` and one `file` (MP4 or MP3). Results
include a source (`subtitles`, `speech`, or `frames`), facts, missing topics,
optional gap, and metadata. Frame facts may have null timestamps only when no
timestamp is available; they cannot produce `Worth it`.

### Health and limits

- `GET /health` returns `{"status":"ok"}`.
- `GET /limits` returns the `limit`, `remaining`, and `resetsAt` values for
  Analyze, Compare, and Media without consuming a request.
- Limited routes include `X-RateLimit-Limit`,
  `X-RateLimit-Remaining`, and `X-RateLimit-Reset` response headers.

## Privacy and storage

- No account is required and the app sets no cookies.
- Browser History stores result summaries on that browser only. It is not
  synced to the server or another device.
- History does not store transcripts, internal quotes, uploaded media, or
  provider token counts.
- Uploaded media is processed in a temporary directory under `DATA_DIR` and
  deleted after the request.
- The rate limiter stores salted HMAC hashes of client addresses rather than
  raw addresses. These hashes are retained for up to two days to enforce
  per-network daily limits.
- Provider API keys are backend-only environment variables; never place them
  in frontend code or commit them.

## Local development

Requirements: Python 3.10+, Node.js 20.19+, and npm.

1. Install backend dependencies:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements-dev.txt
   ```

2. Install frontend dependencies:

   ```powershell
   cd frontend
   npm install
   cd ..
   ```

3. Configure provider keys in the root `.env` file as needed. `.env.example`
   lists available settings. Keep `.env` private and out of source control.

4. Start both Flask and Vite with `start-worthrot.bat`, or run `python main.py`
   and `npm run dev` in separate terminals. The Vite development server proxies
   API requests to Flask.

To serve the production frontend through Flask:

```powershell
cd frontend
npm run build
cd ..
$env:PORT = "5000"
python main.py
```

Flask binds to `0.0.0.0` and uses `PORT` (default `5000`). Local cache data
defaults to `src/backend/data`.

## Configuration

See `.env.example` for the complete list. Main settings include:

| Setting | Default | Purpose |
|---|---:|---|
| `BAZAARLINK_API_KEY` | unset | Required for model analysis. |
| `MODEL_NAME` | `qwen/qwen3.7-flash:free` | Shared text/vision model. |
| `MAX_CONTEXT_TOKENS` | `2500` | Bound model input context. |
| `MAX_VIDEO_MINUTES` | `45` | Maximum transcript/video duration. |
| `MAX_COMPARE_VIDEOS` | `3` | Maximum number of videos in a Compare request. |
| `MAX_UPLOAD_MB` | `100` | Upload size limit. |
| `MAX_MEDIA_SECONDS` | `300` | Upload duration limit. |
| `DATA_DIR` | `src/backend/data` | Cache and temporary-media root. |
| `RATE_LIMIT_PER_FEATURE` | `10` | Default successful daily requests per feature/network. |
| `GEMINI_API_KEY` | unset | Enables speech transcription. |
| `ELEVEN_LABS_API` | unset | Speech transcription fallback credential for Gemini HTTP 429. |

Configure these values in the hosting environment for deployment. Never commit
secrets.

## Tests and build

Run backend tests from the repository root:

```powershell
python -m pytest -q
```

Run frontend tests and build:

```powershell
cd frontend
npm test
npm run build
```

Routine tests mock YouTube and provider calls; they do not require live
credentials. An opt-in live LLM test is documented in `README.md`.

## Project map

- `app.py`, `main.py`: Flask application and entry point.
- `backend/routes/`: health, analysis, comparison, media, and rate-limit APIs.
- `backend/services/`: transcript retrieval, multilingual processing,
  verification, ranking, media processing, and provider integration.
- `backend/prompts/`: model prompts.
- `frontend/src/`: React pages, contexts, components, API client, and styles.
- `tests/`: offline backend tests and transcript fixtures.
- `docs/`: architecture, design system, and architectural decisions.
- `Instructions.md`: consolidated product and feature requirements.
