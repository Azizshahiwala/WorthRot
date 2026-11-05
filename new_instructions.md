---

# Addendum: updates after the initial boilerplate

This section was appended to `AGENTS.md`. **Where it conflicts with an earlier section of this file, this addendum wins**, except for the hosting constraints and the product rules it does not mention, which stay as written above.

## Additional instruction files

Read these before working on the matching feature:

| File | Covers |
|---|---|
| `NEXT_INSTRUCTIONS.md` | Design system, navbar, tabs, context architecture |
| `INSTRUCTIONS_FACTS_PIPELINE.md` | Real `/analyze` pipeline, facts-only output, token budget |
| `INSTRUCTIONS_HISTORY.md` | History tab, browser storage |
| `INSTRUCTIONS_COMPARE.md` | Compare tab and `/compare` |
| `INSTRUCTIONS_ABOUT.md` | About tab (static) |
| `INSTRUCTIONS_OTHER.md` | Other tab, MP4/MP3 uploads, `/analyze-media` |

## Superseded or clarified sections

- **API contract:** replaced by "API contract (current)" below. The old `confidence` and `evidence` fields no longer exist.
- **Product rule 2 ("verify quotes"):** unchanged for transcript paths. On the **frame path** of `/analyze-media` there are no quotes, so facts are verified against the timestamps of the frames sent, labelled as coming from frames, and the verdict is capped at `Skim`. See `INSTRUCTIONS_OTHER.md`.
- **"Handle one URL for now":** `/analyze` still takes one video. Multiple videos go through `/compare`.
- **Code style, "no `localStorage` dependence for core logic":** the only allowed `localStorage` use is the History feature in `src/lib/historyStorage.js`. Core analysis logic must never depend on it.

## Product rules (additions)

1. **Facts only.** Results are short facts with timestamps. No summaries, no paragraphs, in the API or the UI.
2. **Verdicts are computed in code** from verified facts, never by the LLM. Thresholds live in one constants block.
3. **Ranking in `/compare` is computed in code**, never by the LLM. Ordering rules are in `INSTRUCTIONS_COMPARE.md`.
4. **Frame-based results never return `Worth it`.**
5. **Uploads are processed and deleted.** Media files and transcripts are never
   stored beyond the request; successful Other analyses may save only their
   result summary in browser History.
6. **No cookies.** The app sets none.

## API contract (current)

`GET /health` returns `{"status": "ok"}` (unchanged).

### `POST /analyze` (one YouTube video)

Request: `{ "question": "string", "urls": ["string"], "transcript": "string (optional)" }`

Response:

```json
{
  "verdict": "Worth it | Skim | Rot | Can't verify",
  "facts": [{ "text": "string", "timestamp": "mm:ss", "url": "string" }],
  "missing": ["string"],
  "meta": { "video_id": "string", "cached": false, "tokens_in": 0, "tokens_out": 0 }
}
```

### `POST /compare` (2 to 3 YouTube videos)

Request: `{ "question": "string", "urls": ["string", "string"] }`

Response:

```json
{
  "question": "string",
  "best": "video_id or null",
  "ranking": [
    {
      "rank": 1,
      "videoId": "string",
      "url": "string",
      "verdict": "Worth it | Skim | Rot | Can't verify",
      "facts": [{ "text": "string", "timestamp": "mm:ss", "url": "string" }],
      "missing": ["string"],
      "error": null,
      "meta": { "cached": false, "tokens_in": 0, "tokens_out": 0 }
    }
  ],
  "meta": { "tokens_in_total": 0, "tokens_out_total": 0 }
}
```

`best` is `null` unless the top-ranked verdict is `Worth it` or `Skim`. One failing video never fails the request.

### `POST /analyze-media` (one MP4 or MP3 file)

Request: `multipart/form-data` with `question` and `file`.

Response:

```json
{
  "verdict": "Worth it | Skim | Rot | Can't verify",
  "source": "subtitles | speech | frames",
  "facts": [{ "text": "string", "timestamp": "mm:ss or null", "url": null }],
  "missing": ["string"],
  "meta": { "tokens_in": 0, "tokens_out": 0, "frames_sent": 0 }
}
```

### Errors (all endpoints)

Friendly JSON with a human-readable `message`. Required cases: no captions, invalid URL, video too long, transcript blocked, LLM failure, invalid model JSON, unsupported file type, file too large, media too long, `ffmpeg_unavailable`, server busy. Blocked or missing captions must tell the UI to offer the paste-transcript path.

Changing any contract requires updating `models.py`, `src/api.js`, the affected context, result components, tests, and `docs/architecture.md` together.

## Environment variables (consolidated; keep `.env.example` current)

```
# core
DATA_DIR=./data

# analysis (INSTRUCTIONS_FACTS_PIPELINE.md)
MODEL_NAME=
MAX_OUTPUT_TOKENS=300
MAX_CONTEXT_TOKENS=2500
TOP_K_WINDOWS=6
SHORT_TRANSCRIPT_TOKENS=1500
MAX_VIDEO_MINUTES=45

# compare (INSTRUCTIONS_COMPARE.md)
MAX_COMPARE_VIDEOS=3
COMPARE_TIMEOUT_SECONDS=45

# media upload (INSTRUCTIONS_OTHER.md)
MAX_UPLOAD_MB=100
MAX_MEDIA_SECONDS=300
MEDIA_TIMEOUT_SECONDS=90
FFMPEG_TIMEOUT_SECONDS=60
FRAME_INTERVAL_SECONDS=5
FRAME_MAX_SIDE=768
MAX_FRAMES=16
DEDUPE_HAMMING_THRESHOLD=6
FFMPEG_PATH=
BAZAARLINK_API_KEY=
GEMINI_API_KEY=
ELEVEN_LABS_API=
```

Media frame analysis reuses `MODEL_NAME` and `LLM_BASE_URL` (which has the
existing standard Bazaarlink endpoint as its default), so no separate vision
model or provider base URL is needed. Frame and transcript analysis use
`BAZAARLINK_API_KEY`; media speech transcription uses `GEMINI_API_KEY`, with
`ELEVEN_LABS_API` as the fallback credential only when Gemini returns HTTP 429.
All keys must remain backend-only. Never commit secrets.

## Hosting constraints (additions)

- One process, up to 256 MB of memory. Stream uploads to disk, never into memory.
- ffmpeg availability on Embarko is **unverified**. Resolve the binary in this order: `FFMPEG_PATH`, `shutil.which("ffmpeg")`, the `imageio-ffmpeg` bundled binary. If none works, return `ffmpeg_unavailable`.
- Run **one media job at a time**. If busy, return a friendly error.
- Temp files live in `DATA_DIR/tmp/<uuid>/` and are deleted in a `finally` block. Sweep stale directories at app start and at the start of each media request. No timers or background libraries.
- `/compare` may use `concurrent.futures.ThreadPoolExecutor`. Use one SQLite connection per thread with a busy timeout, and confirm the LLM client is thread-safe.
- Flask must serve `frontend/dist/index.html` for any non-API path (catch-all registered after the API routes) so client-side routes survive a refresh.
- Only `backend/services/media/ffmpeg_runner.py` may spawn processes. Rules: `shell=False`, list arguments, timeouts, `-nostdin`, `-protocol_whitelist file`, server-generated filenames only.

## Frontend architecture (current)

Tabs (single source: `src/config/tabs.js`):

| Tab | Route | Status |
|---|---|---|
| YouTube | `/` | Functional (`App()`) |
| Compare | `/compare` | Functional |
| Instagram | `/instagram` | Placeholder |
| Other | `/other` | Functional |
| History | `/history` | Functional |
| About | `/about` | Functional (static) |

Provider order in `main.jsx`:
`BrowserRouter` > `ThemeProvider` > `ToastProvider` > `HistoryProvider` > `AnalysisProvider` > `CompareProvider` > `OtherProvider` > `Layout`

Rules:
- One context per concern. Each file exports the provider and a guarded `useX()` hook. Components never call `useContext` directly.
- The About page is static and needs no context.
- `AnalysisProvider` saves successful single-video analyses and `OtherProvider`
  saves completed media analysis results to History. Compare results are not
  saved. History stores summaries only, never uploaded files or transcripts.
- API calls go through `src/api.js`. For multipart uploads, do not set a JSON `Content-Type`.
- Use design tokens only. No hardcoded colors, spacing, or font sizes. Document every new `ui/` component in `docs/design-system.md`.

## Browser storage

- History uses `localStorage` under the key `worthrot:history:v1`, capped at 50 entries, validated on every load, with every access wrapped in `try/catch`.
- Store only the entry shape defined in `INSTRUCTIONS_HISTORY.md`. Never store transcripts, internal quotes, token counts, or uploaded media.

## Dependencies (approved with justification)

Any other new dependency needs a one-line justification in the commit message.

| Dependency | Where | Why |
|---|---|---|
| `react-router-dom` v6 | frontend | Nested layout routes and active-link handling |
| Vitest | frontend (dev) | No frontend test runner existed |
| Pillow | backend | Perceptual-hash frame dedupe |
| `imageio-ffmpeg` | backend | Fallback ffmpeg binary, since the host may not have one |
| OpenAI-compatible client | backend | BazaarLink text and vision analysis calls |

## Testing (additions)

- Backend: `pytest -q`. Mock the LLM, vision, speech-to-text, and YouTube. No live network calls. Tests needing a real ffmpeg binary use `skipif` when it is missing.
- Frontend: Vitest for pure logic (storage module, validation helpers, data modules, context guards).
- Every change to the chunker, retriever, verifier, ranker, verdict mapping, media validation, or frame dedupe needs a test.

## Docs and ADRs

Keep these current whenever behavior changes:
- `docs/architecture.md`, `docs/design-system.md`, `docs/demo-script.md`
- ADRs in `docs/adr/`: 001-004 (initial), 005 (context and router), 006 (facts-only output and local retrieval), 007 (browser localStorage), 008 (compare endpoint and code ranking), 009 (media upload and frame fallback)

## Definition of done (additions)

- [ ] Vitest passes in addition to `pytest -q` and `npm run build`
- [ ] No cookies are set; no media or transcripts are persisted
- [ ] Contract changes are reflected in every place listed under "API contract (current)"
- [ ] The summary lists anything **not verified**, in particular: real YouTube fetches from the hosted environment, ffmpeg on Embarko, the platform request timeout, BazaarLink speech-to-text support, and the chosen vision model's image limits