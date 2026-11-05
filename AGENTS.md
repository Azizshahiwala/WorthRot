# AGENTS.md: WorthRot

Instructions for AI coding agents working in this repo. Read fully before making changes.

## Project

WorthRot tells a user whether a video covers their question.
Input: a question plus a YouTube URL (or a pasted transcript).
Output: a verdict (`Worth it` / `Skim` / `Rot` / `Can't verify`), concise timestamped facts, and what is missing.
Stretch: rank 1-3 videos for the same question.

Built for the Embarko AI hackathon. Deployed to Embarko (cloud hosting for small apps).

## Stack

- Backend: Python, Flask
- Frontend: React + Vite (built output served by Flask)
- LLM: Bazaarlink OpenAI-compatible API (key via environment variable only)
- Storage: none required; optional SQLite cache in `DATA_DIR`

## Repo layout

```
app.py              Flask entry; serves frontend/dist
backend/routes/     HTTP endpoints (analyze, health)
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
4. **No scraping.** Do not scrape Instagram or download media. Instagram support is paste-transcript only.
5. **Length cap.** Reject or truncate videos over `MAX_VIDEO_MINUTES` (default 45) with a clear message.
6. **Friendly errors.** Handle: no captions, invalid URL, too long, LLM failure. Return a JSON error with a human-readable `message`.

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
