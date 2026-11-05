# AGENTS.md: WorthRot

Instructions for AI coding agents working in this repo. Read fully before making changes.

## Project

WorthRot tells a user whether a video covers their question.
Input: a question plus a YouTube URL (or pasted transcript), or a local MP4/MP3.
Output: a verdict (`Worth it` / `Skim` / `Rot` / `Can't verify`), concise timestamped facts, and what is missing.
Compare: rank 2-3 YouTube videos for the same question. Other: analyze a
user-uploaded MP4 or MP3 without storing it.

Built for the Embarko AI hackathon. Deployed to Embarko (cloud hosting for small apps).

## Stack

- Backend: Python, Flask
- Frontend: React + Vite (built output served by Flask)
- LLM: Bazaarlink OpenAI-compatible API (key via environment variable only)
- Storage: optional SQLite cache in `DATA_DIR`; optional browser `localStorage`
  for per-device analysis history

## Repo layout

```
app.py              Flask entry; serves frontend/dist
backend/routes/     HTTP endpoints (analyze, compare, media, health)
backend/services/   transcript, chunker, verdict, verifier, ranker
backend/prompts/    LLM prompt files
backend/models.py   response schema
frontend/src/       React components and api.js
tests/              pytest tests and transcript fixtures
docs/               architecture.md, adr/, demo-script.md
```

Do not create files outside this layout without a reason stated in the PR or commit message.

## Commands

```bash
# backend
pip install -r requirements.txt
python app.py                 # runs on $PORT (default 5000)
pytest -q                     # run tests

# frontend
cd frontend && npm install
npm run dev                   # dev server
npm run build                 # outputs frontend/dist
```

Run `pytest -q` and `npm run build` before declaring any task done.

## Hard constraints (Embarko hosting)

- Read the port from `PORT` and bind to `0.0.0.0`.
- No WebSockets, no crontab, no background timer libraries. Use plain request/response.
- Persist data only under `DATA_DIR`. The approved local-development default is `src/backend/data`; hosted deployments must supply their persistent `DATA_DIR` and must not store data in the code directory.
- Keep the Embarko manifest at the top of the repo folder. Check https://embarko.ai/docs/quickstart.md for the exact filename and fields before editing it.
- Never hardcode secrets. Read them from environment variables and keep `.env.example` current.

## Product rules (do not violate)

1. **Evidence required.** A `Worth it` or `Skim` verdict must include at least one concise fact with a timestamp.
2. **Verify facts.** `verifier.py` must confirm each fact's internal quote appears in its timestamped transcript window. The internal quote is not returned to the client. Drop or downgrade facts that do not verify.
3. **Never guess.** If there is no transcript or no evidence, return `Rot` or `Can't verify`, never an invented answer.
4. **No media downloads or scraping.** YouTube analysis uses captions or a user-pasted timestamped transcript. The Other tab may process a user's MP4/MP3 upload only.
5. **Length cap.** Reject or truncate videos over `MAX_VIDEO_MINUTES` (default 45) with a clear message.
6. **Friendly errors.** Handle no captions, invalid URL, too long, LLM failure,
   unsupported media, oversized/long media, ffmpeg unavailable, and a busy
   media processor. Return JSON with a human-readable `message`.
7. **Frame evidence exception.** Media facts from sampled frames are checked against timestamps of frames actually sent, labelled "From frames", and verdicts are capped at `Skim`. Untimed speech cannot produce `Worth it` or `Skim`.

## API contract

`POST /analyze`

```json
{ "question": "string", "urls": ["string"], "transcript": "string (optional)" }
```

Response for the single analyzed video:

```json
{
  "verdict": "Worth it | Skim | Rot | Can't verify",
  "facts": [{ "text": "string", "timestamp": "mm:ss", "url": "string" }],
  "missing": ["string"],
  "meta": {
    "video_id": "string",
    "cached": false,
    "tokens_in": 0,
    "tokens_out": 0
  }
}
```

The internal quote used to verify a fact is not returned. For pasted
transcripts without a YouTube URL, the fact's `url` is an empty string.
Errors return a JSON `message`; caption and LLM failures may also include a
`result` with verdict `Can't verify`.
`GET /health` returns `{"status": "ok"}`.

`GET /limits` returns each feature's per-network `limit`, `remaining`, and
`resetsAt` without consuming quota. Every limited route response includes
`X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset` headers.
Quota denials return `429` with a JSON `message`, `code` (`rate_limited` or
`capacity_reached`), `retry_after_seconds`, and `resets_at`, plus `Retry-After`.

`POST /analyze-media` accepts `multipart/form-data` with a question and one
MP4/MP3 file. Its response is:

```json
{
  "verdict": "Worth it | Skim | Rot | Can't verify",
  "source": "subtitles | speech | frames",
  "facts": [{ "text": "string", "timestamp": "mm:ss or null", "url": null }],
  "missing": ["string"],
  "meta": { "tokens_in": 0, "tokens_out": 0, "frames_sent": 0 }
}
```

Uploads are validated by content, size, and duration, processed in
`DATA_DIR/tmp`, and deleted after the request. Successful `/analyze` and
`/analyze-media` results are saved to browser History as summaries only;
Compare results are not saved. Never store uploaded media or transcripts.

`POST /compare` accepts 2 to `MAX_COMPARE_VIDEOS` (default 3) distinct YouTube
URLs and one non-empty question:

```json
{ "question": "string", "urls": ["string", "string"] }
```

It returns the ranked per-video analysis, with `best` set to the top video's ID
only when its verdict is `Worth it` or `Skim`. Individual video failures return
`Can't verify` with an `error.message` and do not fail the request. Ranking
metadata such as coverage and verified-fact counts remain internal.

Each feature allows 10 successful requests per client network per calendar
day by default; failures do not consume quota. Each feature has an independent
counter, and a separate global daily cap protects provider spend. Compare
counts as one request even though it may trigger up to three video analyses.

## Environment variables

Keep `.env.example` current. Rate-limit configuration uses
`RATE_LIMIT_ENABLED`, `RATE_LIMIT_PER_FEATURE`, optional `RATE_LIMIT_ANALYZE`,
`RATE_LIMIT_COMPARE`, and `RATE_LIMIT_MEDIA` overrides,
`GLOBAL_DAILY_CAP_PER_FEATURE`, `RATE_LIMIT_TZ`, `TRUSTED_PROXY_HOPS`,
`RATE_LIMIT_SALT`, and optional `RATE_LIMIT_BYPASS_KEY`. An empty salt is
persisted as a random `0600` file in `DATA_DIR`; only HMAC hashes of client
addresses are stored, and count rows older than yesterday are purged.
The About page explains the hashed-IP retention period and the reason it is
used.
Media configuration uses `MAX_UPLOAD_MB` (100),
`MAX_MEDIA_SECONDS` (300), `MEDIA_TIMEOUT_SECONDS` (90),
`FFMPEG_TIMEOUT_SECONDS` (60), `FRAME_INTERVAL_SECONDS` (5),
`FRAME_MAX_SIDE` (768), `MAX_FRAMES` (16),
`DEDUPE_HAMMING_THRESHOLD` (6), `FFMPEG_PATH`,
`MODEL_NAME`, optional `LLM_BASE_URL`, `GEMINI_API_KEY`, and
`ELEVEN_LABS_API`. Speech transcription uses Gemini when configured and falls
back to ElevenLabs on Gemini HTTP 429; analysis still uses the shared model and
`BAZAARLINK_API_KEY`. Frame analysis defaults to Bazaarlink's standard API
URL. Never expose any key to the frontend.

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

Do not change this schema without updating `models.py`, the frontend, tests, and `docs/architecture.md` together.

## Code style

- Python: PEP 8, type hints on public functions, small single-purpose functions.
- JavaScript: functional React components, hooks, no class components.
- No new dependency without a one-line justification in the commit message. Prefer the standard library.
- No `localStorage` dependence for core logic.
- Comment the why, not the what.

## Testing

- Add or update a test for every change in `chunker.py`, `verifier.py`, and `verdict.py`.
- Use fixtures in `tests/fixtures/`. Do not call the live LLM or YouTube in tests; mock them.

## Workflow

1. Read the relevant file in `docs/` and the matching ADR in `docs/adr/` before changing behavior.
2. Make the smallest change that solves the task. Do not refactor unrelated code.
3. If a task conflicts with an ADR or a hard constraint, stop and ask instead of working around it.
4. If a decision changes, add or supersede an ADR in `docs/adr/` (format: Status, Date, Context, Decision, Options, Trade-offs, Consequences, Action Items).
5. Summarize what changed and what you did not verify.

## Definition of done

- [ ] Tests pass (`pytest -q`)
- [ ] Frontend builds (`npm run build`)
- [ ] App runs locally on `$PORT`
- [ ] No secrets or stray files committed
- [ ] Docs and ADRs updated if behavior changed
