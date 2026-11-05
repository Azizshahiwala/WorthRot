# ADR-008: Compare endpoint and deterministic code ranking

## Status

Accepted

## Date

2026-11-05

## Context

Users need to choose which of two or three videos best answers one question.
The existing `/analyze` pipeline already retrieves timestamped transcript
windows, verifies model-produced facts, and maps evidence to a verdict. Compare
must preserve that evidence pipeline, work when one video fails, and avoid
extra model usage just to order results.

## Decision

Expose `POST /compare` for two to `MAX_COMPARE_VIDEOS` (default 3) distinct
YouTube videos. Run the existing per-video pipeline concurrently with a
`COMPARE_TIMEOUT_SECONDS` (default 45) deadline for each video. Return one
ranked row per input, converting per-video failures and timeouts into
`Can't verify` rows.

Rank in code using verdict tier (`Worth it` > `Skim` > `Rot` > `Can't verify`),
coverage, verified fact count, and stable input order. Only `Worth it` and
`Skim` can be the `best` result. Coverage and verified fact count remain
internal.

The frontend owns Compare state in a separate `CompareContext`, calls the
endpoint through `api.js`, and displays an accessible ranking table followed
by the shared per-video facts panel. Each successfully checked result with a
`Worth it`, `Skim`, or `Rot` verdict is saved as its own History entry through
the existing History context; failed and `Can't verify` rows are not saved.

## Options

- **LLM ranks all videos in one call:** rejected because it adds tokens, asks
  the model to compare results already classified by the pipeline, and makes
  rankings less deterministic.
- **Per-video analysis plus code ranking:** selected because it reuses verified
  results, costs no extra ranking tokens, and gives deterministic,
  explainable tie-breaking.
- **Client-side loop over `/analyze`:** rejected because it leaves ranking,
  concurrency, per-video timeout handling, and partial failures to clients.

## Trade-offs

- Compare may make up to one analysis call per uncached video, but ranking is
  deterministic and adds zero model calls.
- Parallel requests lower overall latency, while each request still has its
  own deadline. A timed-out worker may finish in the background and can still
  complete its cache write.
- Stable input-order tie-breaking makes identical evidence predictable, but
  changing input order can change the order of tied videos.
- A `Can't verify` result ranks last and is explicitly labelled as unchecked,
  rather than being treated as poor video quality.
- SQLite connections are created per worker and use a busy timeout; the
  standard-library HTTP client is per request, so no client state is shared.

## Consequences

- `/analyze` and `/compare` share the reusable single-video pipeline.
- Compare validation failures reject the full request; a failure for one video
  does not prevent other results from being returned.
- Cached video/question results require no additional LLM call.
- The Compare tab is enabled and saves successfully checked results to browser
  History using the existing entry validation, deduplication, and size cap.
- `AGENTS.md`, the architecture contract, design-system docs, and tests must
  stay aligned with the response schema.

## Action Items

- Cover rank tiers, tie-breaks, validation, timeouts, partial failure, caching,
  and the unchanged `/analyze` contract with offline tests.
- Keep the ranking table accessible in both themes and on narrow screens.
- Verify real YouTube caption retrieval from the hosted environment before
  claiming hosted Compare support.
