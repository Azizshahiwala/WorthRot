# ADR-006: Facts-only output and local transcript retrieval

## Status

Accepted

## Date

2026-11-04

## Context

The YouTube analyzer returned a placeholder response. Sending full transcripts
to an LLM is unnecessarily expensive and makes it harder to keep results
verifiable. The product requires timestamped evidence, no invented answers,
and friendly fallback behavior when captions are unavailable.

## Decision

Implement a plain-Python analysis pipeline that fetches caption segments,
cleans and groups them into timestamped windows, ranks windows locally, and
sends only a bounded context to the configured LLM for compact fact extraction. Verify
each returned source quote against the exact timestamped window before
returning the fact. Map coverage and verified-fact counts to verdicts in code.

Return facts, timestamped URLs, missing items, and token/cache metadata.
Internal quotes, confidence scores, summaries, and explanatory prose are not
part of the success response. Cache transcripts by video ID and results by
video ID plus normalized-question SHA-256 in SQLite under `DATA_DIR`.
Transcript-only requests use the same cleaning, windowing, extraction, and
verification stages but are not persisted.

## Options

- Send the full transcript to the LLM.
- Use embeddings or a vector database for retrieval.
- Use local keyword ranking over timestamped windows, with a short-transcript
  shortcut.

## Trade-offs

Local keyword ranking has no additional runtime dependency and avoids tokens
for irrelevant portions of long videos, but can miss paraphrased matches. The
short-transcript shortcut and top-K window limit reduce that risk without
increasing calls for short videos. Quote verification prevents unsupported
facts but may discard a useful fact if the model's quote is not exact.

The `youtube-transcript-api` dependency is required to retrieve caption
segments without downloading media. Cloud providers may be blocked by
YouTube; the API provides the timestamped paste-transcript path instead.
Video length is estimated from transcript timestamps rather than fetched
video metadata.

## Consequences

- A fresh matching request makes at most one LLM API call.
- A cached request makes no LLM call and does not fetch captions again.
- Long transcripts with no relevant windows return `Rot` without an LLM call.
- `MAX_CONTEXT_TOKENS` bounds the question and formatted transcript windows;
  `MAX_OUTPUT_TOKENS` is limited to 300.
- `Worth it` and `Skim` are possible only with verified, timestamped facts.
- Local development defaults cache data to `src/backend/data`; deployments
  supply their persistent `DATA_DIR`.
- The response contract changes and must stay synchronized across backend,
  frontend, tests, and product documentation.

## Action Items

- Keep transcript cleaning, retrieval, verification, and verdict mapping
  covered by offline tests.
- Keep all cache paths inside the configured `DATA_DIR`.
- Revisit retrieval quality if real transcripts show frequent paraphrase
  misses; do not introduce embeddings without measuring the benefit.
- Verify caption access on the hosted platform before claiming hosted
  YouTube-fetch support.
