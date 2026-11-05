# INSTRUCTIONS_FACTS_PIPELINE.md: fast, token-saving YouTube analysis

Read `AGENTS.md` and `NEXT_INSTRUCTIONS.md` first. This file adds to them. If it conflicts with a hard constraint or product rule in `AGENTS.md`, `AGENTS.md` wins. The contract changes below are the one intentional exception, and you must update `AGENTS.md` to match (see "Contract change").

## Goal

Implement the real `/analyze` pipeline for the YouTube feature (it currently returns 501), optimized for **speed and low token use**.

**The output box shows facts only.** No paragraphs, no explanations, no summaries. Each line is one short fact that answers the user's question, with a timestamp.

## Principles

1. Do as much as possible in plain Python. Call the LLM only to extract facts.
2. Send the LLM the smallest useful context, not the whole transcript.
3. Ask for the smallest useful output, with a hard cap.
4. Never trade away the product rules: evidence required, quotes verified, no guessing.

## Pipeline

```
URL -> video_id
  -> cache lookup (video_id + question hash)  --hit--> return
  -> transcript fetch (cached by video_id)
  -> clean + window (30-45 s windows, timestamped)
  -> local retrieval: rank windows against the question, keep top K
  -> LLM: extract facts as compact JSON
  -> verifier: drop facts whose quote is not in the transcript
  -> verdict mapped by rule in code
  -> response (facts only)
```

| Step | File | Notes |
|---|---|---|
| Transcript | `backend/services/transcript.py` | `youtube-transcript-api`; paste-transcript fallback; cache by `video_id` |
| Clean and window | `backend/services/chunker.py` | Strip `[Music]`-style tags and repeated lines. Merge caption lines into 30-45 s windows. Keep start timestamps. |
| Retrieval | `backend/services/retriever.py` | Rank windows against the question locally (see below). Keep top `TOP_K_WINDOWS`. |
| Fact extraction | `backend/services/verdict.py` | One LLM call, JSON out, hard `max_tokens`. |
| Verification | `backend/services/verifier.py` | Every returned quote must appear in the window text (normalized). Drop failures. |
| Cache | `backend/cache.py` | SQLite in `DATA_DIR`: transcripts by `video_id`; results by `video_id + sha256(normalized_question)`. |

## Retrieval (local, no tokens spent)

- Implement keyword ranking (BM25 or TF-IDF) in plain Python. Do **not** add a dependency for this unless justified in the commit message.
- Lowercase, strip punctuation, drop a small stopword list, light stemming optional.
- Score each window against the question. Keep the top `TOP_K_WINDOWS` (default 6), then re-sort them by timestamp.
- **Short video shortcut:** if the full cleaned transcript is under `SHORT_TRANSCRIPT_TOKENS` (default 1500, estimate tokens as `len(text) / 4`), skip retrieval and send it all.
- **Zero-score case:** if no window scores above 0, skip the LLM call and return `Rot` with `facts: []` and `missing: ["no matching content found"]`. This saves a call and is a valid answer.

## LLM call (`verdict.py`)

- Model comes from the `MODEL_NAME` environment variable. Use a small, fast model by default. Do not hardcode a model name.
- `temperature: 0`. `max_tokens` from `MAX_OUTPUT_TOKENS` (default 300).
- Keep the system prompt short and static in `backend/prompts/verdict_prompt.txt`.
- Input format to the model: the question, then retrieved windows as `[mm:ss] text`. Nothing else.
- Required output: JSON only, no prose, no markdown fences:

```json
{
  "coverage": "full | partial | none",
  "facts": [{ "f": "<=15 words", "t": "mm:ss", "q": "<=12-word exact quote" }],
  "missing": ["<=8 words"]
}
```

- Prompt rules to include: state only facts the transcript supports; each fact answers the question; max 5 facts; max 3 `missing` items; no introductions, no explanations, no opinions; if the transcript does not answer, return `coverage: "none"` and empty `facts`.
- Parse defensively: strip stray fences, handle invalid JSON by returning a `Can't verify` result and a friendly error. Never fabricate.
- Record `usage` (input/output tokens) from the API response.

## Verdict mapping (code, not LLM)

Computed **after** verification, from verified facts only:

| Condition | Verdict |
|---|---|
| `coverage == "full"` and at least 2 verified facts | `Worth it` |
| `coverage` is `partial`, or `full` with 1 verified fact | `Skim` |
| 0 verified facts | `Rot` |
| No transcript or LLM failure | `Can't verify` |

Keep the thresholds in one constants block so they are easy to tune.

## Contract change

The response drops long-form fields and confidence. Per video:

```json
{
  "verdict": "Worth it | Skim | Rot | Can't verify",
  "facts": [{ "text": "string", "timestamp": "mm:ss", "url": "string" }],
  "missing": ["string"],
  "meta": { "video_id": "string", "cached": false, "tokens_in": 0, "tokens_out": 0 }
}
```

- The internal verification quote (`q`) is **not** returned to the client by default. It exists only so the verifier can check the fact.
- `url` is the YouTube link with `&t=<seconds>` for the fact's timestamp.
- Update together, in one change: `AGENTS.md` (API contract), `backend/models.py`, `frontend/src/api.js`, `AnalysisContext`, the result components, tests, and `docs/architecture.md`.
- Request contract is unchanged: `{ "question", "urls", "transcript" }`. Handle one URL for now; multi-video ranking is out of scope.

## Frontend changes (follow the design system)

- Replace the verdict card's long layout with a compact **FactsPanel** (or adapt `VerdictCard`) in the existing result area.
- Layout: verdict `Badge`, then a bullet list of facts. Each item is one line: the fact text plus a clickable timestamp link. Below, `missing` items as small muted chips, only if present.
- **No paragraphs, no helper prose, no explanation text** in the result. Empty result: one short line.
- Use existing tokens and `components/ui/` primitives. No hardcoded colors, spacing, or font sizes.
- Keep the loading, error, and success states, and the live-region announcements from the design system.
- Show a small muted line with `tokens_in/out` and a "cached" tag only in development (`import.meta.env.DEV`).
- Update the "Data display" pattern in `docs/design-system.md`.

## Token and speed budget

| Item | Target |
|---|---|
| Context sent to LLM | At most `MAX_CONTEXT_TOKENS` (default 2500) |
| LLM output | At most 300 tokens |
| LLM calls per request | 1 (0 on cache hit or zero-score) |
| Cached repeat request | No LLM call, no transcript fetch |

Enforce `MAX_CONTEXT_TOKENS` by trimming lowest-ranked windows first. Add a test that asserts the cap.

## Config (add to `.env.example`)

```
MODEL_NAME=
MAX_OUTPUT_TOKENS=300
MAX_CONTEXT_TOKENS=2500
TOP_K_WINDOWS=6
SHORT_TRANSCRIPT_TOKENS=1500
MAX_VIDEO_MINUTES=45
DATA_DIR=./data
```

Never hardcode secrets. Hosting constraints from `AGENTS.md` still apply (`PORT`, `0.0.0.0`, no WebSockets, data only in `DATA_DIR`).

## Errors (friendly JSON with a `message`)

No captions, invalid URL, video too long, transcript blocked, LLM failure, invalid model JSON. Blocked or missing captions must tell the UI to offer the paste-transcript path.

## Tests

- `chunker`: cleaning, windowing, timestamps preserved.
- `retriever`: relevant windows ranked first; zero-score returns nothing; context cap enforced.
- `verifier`: a fake quote is dropped; a real quote passes; whitespace and case normalization.
- `verdict`: JSON parsing (valid, fenced, invalid); verdict mapping table; zero verified facts gives `Rot`.
- `/analyze`: success, cache hit (second call makes no LLM call), each error path.
- Mock the LLM and YouTube. Use fixtures in `tests/fixtures/`. No live network calls.

## Docs

- `docs/adr/ADR-006-facts-only-output-and-local-retrieval.md`: decision, options (full transcript to LLM; embeddings; local keyword retrieval), trade-offs (retrieval may miss paraphrased matches; mitigated by the short-video shortcut and top-K), consequences, action items.
- Update `docs/architecture.md` with the new pipeline and contract.
- Update `docs/design-system.md` (Data display pattern).
- Update the sequence diagram if the flow changes.

## Definition of done

- [ ] `/analyze` returns real facts for a YouTube URL; 501 removed
- [ ] Paste-transcript path works through the same pipeline
- [ ] Output shows facts and timestamps only; no paragraphs anywhere in the result box
- [ ] Every returned fact is verified against the transcript; unverified facts are dropped
- [ ] One LLM call per fresh request; zero on cache hit
- [ ] Token cap tests pass; `tokens_in/out` recorded in `meta`
- [ ] `AGENTS.md`, `models.py`, frontend, tests, and docs updated together
- [ ] `pytest -q` and `npm run build` pass
- [ ] Summary lists what changed and what was not verified (especially: real YouTube fetch from the hosted environment)