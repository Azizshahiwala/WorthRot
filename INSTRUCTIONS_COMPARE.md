# INSTRUCTIONS_COMPARE.md: Compare tab (rank 2-3 videos for one question)

Current additive behavior: question gap checks appear in each video result.
After deterministic ranking, one optional request compares verified facts and
returns agreement summaries. Each Compare request is saved as one grouped
History entry. `ADR-012` and `AGENTS.md` define these additions and override
older no-LLM/no-Compare-History statements below; ranking itself remains code-only.

Read `AGENTS.md`, `NEXT_INSTRUCTIONS.md`, `INSTRUCTIONS_FACTS_PIPELINE.md`, and `INSTRUCTIONS_HISTORY.md` first. This file adds to them. If it conflicts with a hard constraint or product rule in `AGENTS.md`, `AGENTS.md` wins. The new endpoint is the one intentional contract addition, and you must update `AGENTS.md` to match.

## Goal

The user asks one question and supplies 2-3 YouTube URLs. WorthRot ranks the
videos by how well each answers the question and compares their verified facts.
Keep summaries concise and grounded in evidence.

## Prerequisite

The single-video pipeline (`INSTRUCTIONS_FACTS_PIPELINE.md`) must work first. Compare reuses it and adds no new analysis logic.

## Scope

**In scope**
1. Refactor the single-video pipeline into a reusable service function
2. `POST /compare` endpoint
3. Ranker service (rules in code, no LLM)
4. Compare tab UI: form, ranking table, per-video facts
5. Enabling the Compare tab in the navbar config
6. Cross-video agreement from verified facts and grouped Compare History

**Out of scope**
- Any non-YouTube source
- Paste-transcript input in Compare (a blocked video becomes `Can't verify`)
- More than 3 videos, accounts, sharing, export

## Backend

### Refactor first

Move the single-video logic out of the `/analyze` route into `backend/services/pipeline.py`:

```python
def analyze_video(question: str, url: str) -> VideoResult: ...
```

- `/analyze` becomes a thin wrapper around it. Its behavior and contract must not change.
- `VideoResult` carries the public fields (`verdict`, `facts`, `missing`, `meta`) plus the internal `coverage` and `verified_fact_count`. The internal fields are used by the ranker and are **not** returned to the client.
- `analyze_video` must never raise to the caller for expected failures. Return a result with verdict `Can't verify` and an `error` message instead.

### Endpoint

`POST /compare`

Request:

```json
{ "question": "string", "urls": ["string", "string"] }
```

Validation (return a friendly JSON error with a `message`):
- `question` required and non-empty
- 2 to `MAX_COMPARE_VIDEOS` (default 3) URLs
- Each must be a valid YouTube URL
- Reject duplicates (compare by extracted `video_id`)

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
      "gap": {
        "covered": 1,
        "total": 2,
        "label": "Partly covered",
        "parts": [{"text": "question part", "status": "covered"}]
      },
      "error": null,
      "meta": { "cached": false, "tokens_in": 0, "tokens_out": 0 }
    }
  ],
  "agreement": {
    "agree": [{"point": "string", "videos": ["A", "B"]}],
    "disagree": [{"point": "string", "positions": [
      {"video": "A", "claim": "string"},
      {"video": "B", "claim": "string"}
    ]}],
    "unanswered": ["string"]
  },
  "meta": { "tokens_in_total": 0, "tokens_out_total": 0 }
}
```

- `best` is the top-ranked video's id **only if** its verdict is `Worth it` or `Skim`. Otherwise `null` (none of the videos covers the question).
- `error` is `null` or `{ "message": "string" }` for videos that failed.
- The request fails as a whole only on validation errors. A failure in one video must not fail the others.

### Running videos

- Run `analyze_video` for each URL in parallel with `concurrent.futures.ThreadPoolExecutor` (standard library, no new dependency). No background timers, no WebSockets, which keeps the Embarko constraints.
- Set a per-video timeout (`COMPARE_TIMEOUT_SECONDS`, default 45). On timeout, that video becomes `Can't verify`.
- Cache hits still apply per video, so repeated compares can cost zero LLM calls.
- When at least two results have verified facts, make one short, bounded
  agreement request using only the question and those facts. The call is
  optional, its tokens count toward Compare totals, and failure returns
  `agreement: null` without affecting rank or `best`.
- **Thread safety:** open a SQLite connection per thread, set a busy timeout, and confirm the LLM client is safe to share across threads (otherwise create one per call).

### Ranker (`backend/services/ranker.py`)

Pure function, no I/O, no LLM. Sort key, in order:

1. Verdict tier: `Worth it` > `Skim` > `Rot` > `Can't verify`
2. `coverage`: `full` > `partial` > `none`
3. `verified_fact_count`, descending
4. Original input order (stable, deterministic)

Rules:
- `Can't verify` always ranks last. It means the video could not be checked, not that it is bad. Its row must say so.
- Assign distinct ranks 1..N.
- Do not rank on fact count alone, since longer videos naturally yield more facts.
- Keep the tier order and thresholds in one constants block.

### Config (add to `.env.example`)

```
MAX_COMPARE_VIDEOS=3
COMPARE_TIMEOUT_SECONDS=45
```

## Frontend (follow the design system and context rules)

New context, per the one-context-per-concern rule:

| Hook | Holds | Actions |
|---|---|---|
| `useCompare()` | `question`, `urls` (array), `status` (`idle`/`loading`/`success`/`error`), `result`, `error` | `setQuestion`, `setUrl(index, value)`, `addUrl`, `removeUrl(index)`, `compare()`, `reset()` |

- Provider plus guarded hook, memoized value, no JSX or inline fetch in the context. API calls go through `src/api.js` (add `compare()` there).
- New provider order: `BrowserRouter` > `ThemeProvider` > `ToastProvider` > `HistoryProvider` > `AnalysisProvider` > `CompareProvider` > `Layout`.
- In `config/tabs.js`, enable Compare and remove its "Soon" badge. Replace the `ComingSoon` page with the real `ComparePage`.

Components (`components/compare/`, one per file):

| Component | Purpose |
|---|---|
| `CompareForm.jsx` | Question input, 2-3 URL inputs, add/remove URL controls, submit with loading state. Built from existing `Input` and `Button`. |
| `RankTable.jsx` | Semantic `<table>`: rank, video, verdict `Badge`, verified fact count, link to the first fact timestamp |
| `CompareResultList.jsx` | Per-video facts in rank order, reusing the **same facts panel** as the YouTube tab |
| `AgreementBlock.jsx` | Shaded agree/disagree/unanswered lines, mapping video letters to ranks and IDs |

UI rules:
- Put the agreement block between the rank table and per-video results. Keep
  its three labelled lines shaded and identify videos by letter, rank, and ID.
- Keep each result grounded in verified facts. If any agreement list is empty,
  show a short plain-text fallback.
- If `best` is `null`, show one line: "None of these videos cover your question."
- A `Can't verify` row shows the short error message and the label "Could not check".
- Table accessibility: `<caption>`, `<th scope>`, a verdict text label (not color alone), keyboard-reachable links. On narrow screens (below 640px) the table scrolls inside its own container or stacks as cards.
- Add/remove URL buttons have accessible names; the minimum is 2 inputs and the maximum is 3 (disable "add" at the cap).
- Loading: disable the form, show the `Spinner` with a status label. Results announce through the existing polite live region; errors use alert semantics.
- Use only existing tokens and `components/ui/` primitives. No hardcoded colors, spacing, or font sizes.
- In development only (`import.meta.env.DEV`), show the total token counts.

## Tests

Backend (pytest, mock the LLM and YouTube, no live network):
- `ranker`: table-driven tests for tier order, coverage tiebreak, fact count tiebreak, stable input-order tiebreak, `Can't verify` always last, and `best` being `null` when no video is `Worth it` or `Skim`.
- `/compare` validation: missing question, fewer than 2 URLs, more than the cap, invalid URL, duplicate video.
- Partial failure: one video raises or times out, the others still return and the failed one is `Can't verify`.
- Cache: a repeated compare makes no LLM call for cached videos.
- History: save one grouped Compare entry with ranking, per-video verified
  facts, and nullable agreement; do not store transcripts or internal quotes.
- `/analyze` contract unchanged after the refactor.

Frontend (Vitest): `useCompare` guard error outside provider, URL add/remove bounds (min 2, max 3), and any URL validation helper.

## Docs

- `docs/adr/ADR-008-compare-endpoint-and-code-ranking.md`: decision, options (LLM ranks all videos in one call; per-video analysis plus code ranking; client-side loop over `/analyze`), trade-offs, consequences, action items. Record why ranking is in code (zero extra tokens, deterministic, explainable).
- `docs/adr/ADR-012-gap-agreement-and-compare-history.md`: current gap,
  agreement, and History behavior.
- Update `AGENTS.md`, `docs/architecture.md`, and `docs/design-system.md` with
  the response fields, shaded summaries, and grouped Compare History.
- Update the sequence diagram for the multi-video flow if you maintain it.

## Definition of done

- [ ] `/compare` ranks 2-3 videos and returns the contract above
- [ ] `/analyze` still passes its tests, unchanged
- [ ] One failing video does not fail the whole compare
- [ ] `Can't verify` ranks last and is labelled "Could not check"
- [ ] `best` is `null` and the UI says so when nothing covers the question
- [ ] N videos cost at most N analysis calls plus one optional agreement call
- [ ] Gap check only appears when question parts are available
- [ ] Agreement failure leaves ranking visible and unchanged
- [ ] Compare History expands to the saved ranking, agreement, and per-video facts
- [ ] Accessible table, keyboard-navigable, light and dark themes both correct
- [ ] No hardcoded colors, spacing, or font sizes
- [ ] ADR-008, `AGENTS.md`, `architecture.md`, and design-system docs updated
- [ ] `pytest -q`, Vitest, and `npm run build` pass
- [ ] Summary lists what changed and what was not verified (especially real YouTube fetches from the hosted environment)