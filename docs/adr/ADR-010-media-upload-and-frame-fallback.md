# ADR-010: Process user-uploaded MP4 and MP3 media

## Status

Accepted

## Date

2026-11-05

## Context

WorthRot needs an Other workflow for users who have a local MP4 or MP3 rather
than a YouTube URL. Hosting is memory-constrained and does not guarantee
ffmpeg, while untrusted media can abuse protocol handlers or retain sensitive
content. Frame-only evidence also cannot establish the same depth of coverage
as verified timestamped transcript quotes.

## Decision

Add `POST /analyze-media` for one MP4 or MP3 upload. Validate its magic bytes,
size, duration, and usable streams. Stream it into a generated directory under
`DATA_DIR/tmp/<uuid>/`; permit one media job at a time; always remove the
directory and sweep workdirs older than one hour at startup and request start.

Resolve ffmpeg from `FFMPEG_PATH`, `shutil.which`, then `imageio-ffmpeg`.
Only `backend/services/media/ffmpeg_runner.py` may spawn ffmpeg or ffprobe.
Use argument lists, `shell=False`, bounded timeouts, local-file protocol
whitelisting, fixed resource flags, and generated input/output names.

For MP4, prefer embedded timed subtitles, then Gemini timestamped speech
transcription when `GEMINI_API_KEY` is configured, then sampled, deduplicated
frames sent in one vision request. If Gemini returns HTTP 429 and
`ELEVEN_LABS_API` is configured, retry transcription through ElevenLabs using
word-level timestamps; do not retry ElevenLabs for other Gemini errors. MP3
uses the same speech transcription path. Speech segments without valid
in-range timestamps are discarded. Frame facts must cite timestamps of frames
actually sent and are capped at `Skim`; zero verified frame facts returns
`Rot`. Other result summaries may be saved to browser History, but not uploads
or transcripts. Compare results are not saved.

Frame analysis reuses the configured `MODEL_NAME` and `LLM_BASE_URL`, with the
same standard Bazaarlink endpoint default as transcript analysis. It requires
only `BAZAARLINK_API_KEY` for provider authentication; no separate vision
model or provider URL setting is required. Gemini STT uses `GEMINI_API_KEY`
when configured and falls back to ElevenLabs on HTTP 429 when
`ELEVEN_LABS_API` is available.

## Options

- **Provider-native video input:** rejected because model support and image
  limits vary and cannot be verified consistently.
- **Client-side frame extraction:** rejected because it exposes processing
  details to the browser and cannot enforce the server's validation and caps.
- **Python ffmpeg binding:** rejected in favor of a small subprocess boundary
  with explicit arguments, timeouts, and protocol restrictions.
- **Transcript-first with frame fallback:** selected to reuse existing
  timestamped transcript verification where possible and keep visual claims
  tied to the exact sampled frames otherwise.

## Trade-offs

- Frame sampling may miss events between sampled timestamps; the verdict cap
  prevents sparse visual evidence from receiving `Worth it`.
- The host may not have ffmpeg, the platform may time out requests, either
  transcription provider can fail or provide unusable timestamps, and the
  shared configured model may not support image inputs or the selected image
  count.
- ImageIO's bundled ffmpeg adds a dependency and disk footprint but provides a
  fallback binary.
- Gemini timestamps are model-generated, so malformed and out-of-range
  segments are rejected; valid times still depend on transcription quality.

## Consequences

- `/analyze-media`, its response type, Vite proxy, Other tab, upload context,
  and shared facts panel support nullable timestamps.
- The frontend and backend enforce the same file-size limit; server validation
  remains authoritative and uses content rather than extension or MIME type.
- Uploads, extracted audio, subtitles, and frames are temporary and deleted;
  browser History retains only media result summaries.
- Pillow supports perceptual dHash deduplication; `imageio-ffmpeg` provides the
  configured binary fallback.
- ADR-011 records that History may store Other result summaries without
  retaining uploaded media or transcripts. ADR-009 remains the decision to
  remove Instagram analysis.

## Action Items

- Keep `AGENTS.md`, `.env.example`, API docs, and design-system docs aligned.
- Mock providers and YouTube in tests; cover magic bytes, caps, subprocess
  options, frame deduplication/timestamps, route errors, and cleanup.
- Before claiming hosted support, verify ffmpeg availability on Embarko, its
  proxy request timeout, Gemini and ElevenLabs API access, and the shared
  model's image support and limits.
