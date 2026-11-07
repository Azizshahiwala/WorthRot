# WorthRot Instructions

This file consolidates the project and feature requirements from the
repository-root instruction briefs. The `docs/` folder was intentionally not
used as a source for this consolidation. The original briefs remain in place
for traceability; where an older brief conflicts with the current behavior
below, follow this consolidated document and `AGENTS.md`. `AGENTS.md` remains
the companion authority for repository workflow and hosting constraints.

## Product

WorthRot helps a person decide whether a video answers their question. It
accepts a YouTube URL or pasted timestamped transcript, and user-uploaded MP4
or MP3 media. It returns a verdict, short timestamped facts, missing topics,
and an optional question gap check. Compare ranks multiple YouTube videos for
one question.

The interface includes YouTube, Compare, Other, History, and About. Instagram
is a placeholder and is not analyzed.

## Non-negotiable behavior

- Valid verdicts are `Worth it`, `Skim`, `Rot`, and `Can't verify`.
- `Worth it` and `Skim` require at least one verified, timestamped fact.
- Facts must be grounded in transcript evidence. The internal quote must be
  found in the timestamped transcript window; quotes are not returned to the
  client.
- Never invent evidence. Without usable evidence, return `Rot` or
  `Can't verify`.
- Keep result text concise and factual; do not return summaries or explanatory
  paragraphs as facts.
- YouTube processing uses captions or a user-pasted timestamped transcript.
  Do not download or scrape YouTube media.
- Process only user-uploaded MP4 and MP3 files in the Other feature. Delete
  uploads and temporary processing files after the request.
- Frame-derived facts must cite timestamps of frames that were actually sent,
  be identified as frame evidence, and never produce `Worth it`.
- Show friendly JSON errors for invalid input, unavailable captions, length
  limits, provider failures, unsupported media, oversized uploads, ffmpeg
  failures, and a busy media processor.

## Analysis and evidence pipeline

- Parse the YouTube video ID, then use cached analysis/transcript data where
  available.
- Parse pasted transcripts through the same analysis pipeline as captions.
- Clean and group timestamped caption segments into transcript windows while
  preserving the source segments.
- Retrieve relevant windows locally with plain Python; send only bounded,
  useful context to the configured model.
- Short transcripts can bypass keyword retrieval when they fit the configured
  context limit. If no relevant windows are found, return `Rot` without an
  extraction call.
- Request compact JSON facts, question gaps, and exact source quotes. Validate
  the model response defensively.
- Verify each quote against the source transcript window and use the caption
  segment containing the quote for its timestamp when possible. Keep displayed
  timestamps accurate; YouTube links may lead in by two seconds, floored at
  zero.
- Map verdicts in code from coverage and verified facts, not from an
  unverified model verdict.
- Keep cache files under `DATA_DIR`. Cached results must remain compatible
  with older entries that may lack optional fields.

### Multilingual behavior

- Support multilingual captions and transcript content with provider language
  codes where available and lightweight language/script heuristics otherwise.
- Prefer usable manual captions, then generated captions, and only then
  translated captions according to the language-selection rules in the
  transcript service.
- For a long transcript in a different language from the question, translation
  of the question is retrieval-only. Do not translate the transcript or use a
  translated question as evidence. If translation fails, continue with
  best-effort retrieval and expose the failure in metadata.
- Write facts and missing topics in the question language. Keep internal
  quotes in the source language and verify them against that source.
- Use script-aware tokenization and context estimates. Preserve meaningful
  Indic and Arabic combining marks and preserve ZWJ/ZWNJ during quote
  normalization.
- Label the detected transcript language and source in results. Detection is
  heuristic when reliable upstream metadata is unavailable; do not promise
  complete support for every language.
- Add `lang` and automatic text direction to multilingual content and provide
  sensible font fallbacks.

## Question gap checks

- The analysis response may break a question into at most four short parts,
  each marked `covered`, `partial`, or `missing`.
- Determine coverage only from supplied transcript windows. Cap covered parts
  by the number of verified facts; with zero verified facts, every part is
  missing.
- Preserve the existing `missing` list. A gap check is an additional summary,
  and may be `null` or absent in legacy cache entries.
- Display the check in YouTube, Other, Compare video results, and History.
  Hide the UI when gap data or parts are unavailable.

## Compare

- Accept one non-empty question and two to `MAX_COMPARE_VIDEOS` (default 3)
  distinct YouTube video IDs. Do not accept pasted transcripts in Compare.
- Analyze videos concurrently with a bounded per-video timeout. A failure or
  timeout for one video becomes a `Can't verify` row and must not fail the
  other videos.
- Rank deterministically in code: verdict tier, coverage, verified fact count,
  then original input order. `Can't verify` ranks last. Never rank with an LLM.
- Set `best` only when the leading verdict is `Worth it` or `Skim`; otherwise
  return `null`.
- Optionally compare verified facts from at least two videos to describe
  agreement, disagreements, and unanswered question aspects. Never compare
  transcripts or infer beyond verified facts. Agreement failure must not
  change the ranking or fail the request.
- Include agreement token usage in Compare totals.
- Save a completed Compare as one grouped History entry.

## Other: uploaded media

- Accept exactly one MP4 or MP3 upload, validated by file content, not filename
  or claimed MIME type. Enforce both size and duration caps.
- Stream uploads to disk under `DATA_DIR/tmp`; do not hold full media files in
  memory. Use the existing single-media-job capacity guard and total timeout.
- For MP4, prefer embedded subtitles, then speech transcription when
  configured, then sampled and deduplicated frames. MP3 uses speech
  transcription; without a usable transcript, return `Can't verify`.
- Use Gemini for speech transcription when configured and fall back to
  ElevenLabs on Gemini HTTP 429 only. Reject missing or out-of-range speech
  timestamps.
- Frame analysis makes one bounded vision call, validates evidence against
  sent frame timestamps, and caps a positive verdict at `Skim`.
- `backend/services/media/ffmpeg_runner.py` is the only module that may spawn
  ffmpeg processes. Use argument lists, `shell=False`, timeouts, local-file
  protocol restrictions, and server-generated filenames; never return raw
  ffmpeg output to clients.
- Delete the request work directory on success and failure. Do not save uploads
  or transcripts in History.

## History and privacy

- History is per browser/device in `localStorage`, not an account or server
  feature. Set no cookies.
- Validate stored data on every load. Handle blocked, malformed, and full
  storage without breaking analysis. Cap History at 50 entries.
- Save successful result summaries only. Do not store transcripts, internal
  quotes, uploads, secrets, or provider token counts.
- Deduplicate repeated single-video analyses by video and normalized
  question. Keep completed Compare results in one grouped entry.
- Rate limiting stores only salted HMAC hashes of client network addresses,
  never raw addresses. Explain the purpose and up-to-two-day retention on
  About.

## Rate limits

- Limit `/analyze`, `/compare`, and `/analyze-media` independently to 10
  successful requests per client network per calendar day by default.
  Failures release reserved quota; successful `Can't verify` responses count.
- Compare counts as one request regardless of how many videos are checked.
- Enforce the separate global provider-spend cap (default 200 per feature),
  with configurable per-feature overrides.
- Enforce limits before expensive provider or media work. Fail closed if
  limiter storage is unavailable.
- Keep the separate global daily cap, configurable per-feature overrides,
  trusted proxy hop handling, optional demo bypass, and `GET /limits`.
- Limited responses include `X-RateLimit-Limit`,
  `X-RateLimit-Remaining`, and `X-RateLimit-Reset`. Quota denials return a
  friendly `429` JSON response and `Retry-After`.

## Frontend and About

- Use functional React components and one context per concern. Context hooks
  are guarded and values/actions are memoized; API calls go through
  `frontend/src/api.js`.
- Tabs are driven by one configuration. Keep components keyboard accessible,
  use semantic controls and visible focus, and use design tokens rather than
  hardcoded colors, spacing, or font sizes.
- Keep the About page static, with copy in its configuration. Explain the
  product, workflow, principles, honest limits, privacy, and recent changes.
  Highlight **Support for multi-languages**. Never invent author details.
- Preserve timestamp precision improvements. Use accessible icons for
  decorative controls rather than relying on text glyphs alone.

## API contracts

### `POST /analyze`

Request: `{ "question": "string", "urls": ["string"], "transcript": "string (optional)" }`.
Analyze at most one video URL; a timestamped pasted transcript may be used
instead.

Successful results contain `verdict`, `facts`, `missing`, optional `gap`, and
`meta`. A fact contains `text`, `timestamp`, and `url`. Metadata includes
`video_id`, cache/token information, question/transcript/original language,
transcript source, and the retrieval-translation failure flag. Internal quotes
are never returned.

### `POST /compare`

Request: `{ "question": "string", "urls": ["string", "string"] }`.
Return `question`, `questionLanguage`, nullable `best`, ranked per-video
results, optional `gap` per result, nullable `agreement`, and aggregate token
usage. A failed video has an `error.message`; it does not fail the request.

### `POST /analyze-media`

Accept multipart form data with a `question` and one `file`. Return verdict,
source (`subtitles`, `speech`, or `frames`), facts, missing topics, optional
gap, and token/frame/language metadata. A media fact may have a null timestamp
and uses `url: null`.

### Supporting endpoints

- `GET /health` returns `{"status": "ok"}`.
- `GET /limits` returns the current per-feature quota without consuming it.

Errors use JSON with a human-readable `message`. Keep response models,
frontend API handling, components, tests, and `docs/architecture.md`
synchronized whenever a contract changes.

## Hosting and configuration

- Flask reads `PORT` (default 5000) and binds to `0.0.0.0`.
- Do not add WebSockets, background workers, timer libraries, or cron jobs.
- Persist application data only under `DATA_DIR`; hosted deployments must
  provide persistent storage.
- Never hardcode or expose provider keys. Keep `.env.example` current.
- Read `.env.example` for the canonical settings and defaults, including
  analysis, media, rate-limit, and storage options.

## Tests and completion

- Backend: `python -m pytest -q`; frontend: `npm test` from `frontend`;
  production frontend: `npm run build`.
- Mock YouTube, model, speech, and vision providers in tests. Do not use live
  services in routine tests.
- Add tests for changed logic, especially retrieval, verification, verdicts,
  rate limits, media validation, ranking, and History validation.
- Before completion, run backend tests and the frontend build/tests, check
  `git diff --check`, and state what could not be verified in the target
  hosting environment.

## Consolidated repository-root briefs

This document combines requirements and decisions from:

- `WORTHROT-IMPROVEMENTS_1.md`
- `IMPROVEMENTS_2.md`
- `LANGUAGE.md`
- `youtube-feature.md`
- `Next-instructions.md`
- `new_instructions.md`
- `INSTRUCTIONS_ABOUT.md`
- `INSTRUCTIONS_COMPARE.md`
- `INSTRUCTIONS_OTHER.md`
- `INSTUCTIONS_HISTORY.md`
- `SPECIAL_LIMIT.md`
