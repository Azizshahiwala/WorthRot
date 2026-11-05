# INSTRUCTIONS_OTHER.md: "Other" tab (MP4 and MP3 uploads)

Read `AGENTS.md`, `NEXT_INSTRUCTIONS.md`, `INSTRUCTIONS_FACTS_PIPELINE.md`, and `INSTRUCTIONS_HISTORY.md` first. This file adds to them. If it conflicts with a hard constraint or product rule in `AGENTS.md`, `AGENTS.md` wins. This file makes **two intentional exceptions**, both listed under "Contract and rule changes", and you must update `AGENTS.md` to match.

## Goal

The user uploads an **MP4 or MP3** file and asks a question. WorthRot returns facts only (no paragraphs), reusing the existing output format.

Extraction order:
1. Transcript from the file itself (embedded subtitles, then speech-to-text)
2. If no transcript is available (MP4 only): extract unique frames and send them to a vision model in one call

## Scope

**In scope**
1. New route `POST /analyze-media` and a media service package
2. MP4 and MP3 only, validated by content (not extension)
3. Subtitle extraction, Gemini speech-to-text, and the frame fallback
4. "Other" tab and its context, form, and result display
5. Safe `ffmpeg` execution, upload caps, and temp file cleanup

**Out of scope**
- Any other format (MOV, WebM, MKV, WAV, M4A, images, URLs)
- Client-side video compression (ffmpeg.wasm is too heavy)
- Saving uploaded media files or transcripts to History
- Background jobs, progress streaming, or WebSockets (Embarko does not support them)
- Multiple files, Compare integration, accounts

## Hosting facts that shape this design

- Embarko runs **one process, up to 256 MB of memory, no background workers, no WebSockets**. Process inside the request.
- No Dockerfile is allowed, and the docs do not say ffmpeg is installed. **Do not assume it.**
- All temp data goes under `DATA_DIR`, never next to the code.
- Stream uploads to disk. **Never read a whole file into memory.**

## Resolution and upload caps

Two separate controls. Do not confuse them.

| Control | Purpose | Where |
|---|---|---|
| **Upload cap** | Limits the upload stream itself | Browser checks `file.size` before sending; server enforces `MAX_CONTENT_LENGTH` and rejects over `MAX_UPLOAD_MB` |
| **Mid-resolution resize** | Limits CPU, memory, and image tokens | Inside the same ffmpeg command that extracts frames (no separate transcode) |

- Resizing on the server cannot shrink an upload that has already been sent. The size cap does that job. Do not build a separate full-video transcode.
- Frame resize filter: longest side at most `FRAME_MAX_SIDE` (default 768 px), aspect ratio preserved, even dimensions:
  `scale=768:768:force_original_aspect_ratio=decrease:force_divisible_by=2`

## Config (add to `.env.example` and a `config/limits.js` mirror on the frontend)

```
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

- Frame analysis reuses `MODEL_NAME` and `LLM_BASE_URL`, including the existing
  standard Bazaarlink API URL default. `BAZAARLINK_API_KEY` is the only
  provider setting required for frame analysis.
- When `GEMINI_API_KEY` is configured, use Gemini audio transcription
  automatically if an audio stream has no embedded subtitles. Request
  timestamped speech segments and reject timestamps outside the validated
  media duration. On Gemini HTTP 429 rate-limit/quota responses only, use
  ElevenLabs Speech-to-Text with `ELEVEN_LABS_API` and word timestamps. No
  separate STT model or enable flag is required.
- The frontend mirror holds only `MAX_UPLOAD_MB` and the allowed types, for the pre-upload check.
- Never hardcode secrets.

## Pipeline

```
upload (stream to DATA_DIR/tmp/<uuid>/) -> validate type, size, duration
  MP4:
    1) embedded subtitle stream?  -> text transcript (timed)
    2) GEMINI_API_KEY? -> extract audio -> Gemini STT -> ElevenLabs on HTTP 429
       -> transcript
    3) otherwise frames: sample -> dedupe -> cap -> one vision call
  MP3:
    1) GEMINI_API_KEY? -> Gemini STT -> ElevenLabs on HTTP 429 -> transcript
    2) otherwise: friendly error ("No transcript available for audio-only files")
transcript path -> existing windowing, retrieval, LLM, verifier, verdict mapping
frame path      -> frame verifier, capped verdict mapping
finally: delete the temp directory
```

Chunking is **not** needed. At the 5-minute cap, extracted mono audio is small, and one ffmpeg pass handles frames.

## Backend structure

```
backend/
├── routes/media.py              # POST /analyze-media
└── services/media/
    ├── validate.py              # magic bytes + probe, size and duration caps
    ├── ffmpeg_runner.py         # the ONLY place that runs ffmpeg
    ├── subtitles.py             # embedded subtitle extraction
    ├── audio.py                 # audio extraction for STT
    ├── stt.py                   # speech-to-text adapter (feature flagged)
    ├── frames.py                # sampling, resize, dedupe, capping
    ├── vision.py                # BazaarLink OpenAI-compatible call
    └── workdir.py               # temp dir create/cleanup/sweep
```

### ffmpeg resolution

Resolve the binary in this order: `FFMPEG_PATH` env var, then `shutil.which("ffmpeg")`, then the `imageio-ffmpeg` package's bundled binary (add it as a dependency with a justification, since the host may have no ffmpeg). If none works, return the friendly error `ffmpeg_unavailable`. Do not change `/health`. Log which binary was found at startup.

### Running ffmpeg (security: this is the only isolation Embarko gives)

`ffmpeg_runner.py` is the **only** code allowed to spawn processes. Rules:
- `subprocess.run([...], shell=False, timeout=FFMPEG_TIMEOUT_SECONDS, check=False, capture_output=True)`. Arguments are a list, never a string, never built from user text.
- Always pass `-nostdin -hide_banner -loglevel error -threads 1`.
- Restrict inputs to local files with `-protocol_whitelist file` placed before `-i`. Crafted media can otherwise make ffmpeg read URLs or other local files.
- Use only server-generated filenames (`input.mp4`, `input.mp3`, `frame_%04d.jpg`). Never use the uploaded filename on disk.
- No terminal or PTY. A virtual terminal adds risk and no value.
- Capture and truncate stderr for logs. Never return raw ffmpeg output to the client.

Example frame command (the agent may adapt it, keeping the rules above):

```
ffmpeg -nostdin -hide_banner -loglevel error -threads 1 -protocol_whitelist file \
  -i input.mp4 \
  -vf "fps=1/5,scale=768:768:force_original_aspect_ratio=decrease:force_divisible_by=2" \
  -q:v 5 -frames:v 60 frames/frame_%04d.jpg
```

### Validation (`validate.py`)

- Accept only MP4 and MP3, decided by **content**: MP4 has `ftyp` at bytes 4-8; MP3 starts with `ID3` or an MPEG frame sync. The extension and MIME type are hints only.
- Confirm streams and duration with an ffmpeg probe (parse its stderr; `ffprobe` may not exist). Reject: no usable stream, duration over `MAX_MEDIA_SECONDS`, size over `MAX_UPLOAD_MB`.
- Set `MAX_CONTENT_LENGTH` in Flask and return a friendly JSON error on 413.

### Subtitles and speech-to-text

- `subtitles.py`: if the MP4 has a subtitle stream, extract the first one to SRT and parse it into timed segments. If none, return nothing.
- `audio.py`: extract mono, 16 kHz, low-bitrate audio (`-vn -ac 1 -ar 16000`, MP3 at about 48 kbps).
- `stt.py`: use the Gemini `generateContent` audio input with
  `GEMINI_API_KEY`. Request structured transcription segments with start
  timestamps; discard missing or out-of-range timestamps so untimed speech
  cannot support a positive verdict. Only Gemini HTTP 429 triggers fallback
  to ElevenLabs `POST /v1/speech-to-text` with `ELEVEN_LABS_API`; parse its
  word timestamps into transcript segments. If both providers are unavailable,
  MP4 falls back to frames and MP3 returns `Can't verify`.
- Transcript output feeds the **existing** pipeline. For untimed text, split into windows by length and omit timestamps and links.

### Frame path (`frames.py`, `vision.py`)

1. Sample one frame every `FRAME_INTERVAL_SECONDS`, resized as above. Frame `n` (1-based) has time `(n-1) * interval`.
2. **Dedupe** consecutive frames with a perceptual hash (dHash via Pillow; add Pillow with a justification). Drop a frame if its Hamming distance to the last kept frame is at most `DEDUPE_HAMMING_THRESHOLD`.
3. If more than `MAX_FRAMES` remain, keep an evenly spaced subset.
4. Send **one** chat completion with the question plus all frames as base64 `image_url` parts, `temperature: 0`, `max_tokens` 300, through the OpenAI-compatible client pointed at `LLM_BASE_URL` using `MODEL_NAME`.
5. Required JSON only, same compact shape as the text pipeline, where `t` is the frame's timestamp:

```json
{ "coverage": "full | partial | none",
  "facts": [{ "f": "<=15 words describing what is visible or shown", "t": "mm:ss" }],
  "missing": ["<=8 words"] }
```

Prompt rules: describe only what is visible in the frames; each fact answers the question; max 5 facts; no explanations; if the frames do not answer it, return `coverage: "none"` with empty facts.

6. **Frame verifier:** drop any fact whose `t` is not the timestamp of a frame that was sent. Quotes do not exist on this path.
7. Delete frames immediately after the call.

### Verdict mapping

| Path | Rule |
|---|---|
| Subtitles or speech-to-text | Same table as `INSTRUCTIONS_FACTS_PIPELINE.md` |
| Frames | `full` or `partial` with at least 1 verified fact gives **`Skim` at most**. 0 verified facts gives `Rot`. Never `Worth it`. |
| No transcript, STT off, MP3 | `Can't verify` with the friendly message |
| Any failure | `Can't verify` |

Keep the cap in the one constants block.

### Concurrency and cleanup

- Allow **one media job at a time** (a non-blocking `threading.BoundedSemaphore(1)`). If busy, return a friendly "busy, try again shortly" error. This protects the 256 MB limit.
- Create `DATA_DIR/tmp/<uuid>/` per request and delete it in a `finally` block, including on errors and timeouts.
- No timers or background libraries. Sweep temp directories older than 1 hour at app start and at the beginning of each media request.
- Enforce `MEDIA_TIMEOUT_SECONDS` as the total request budget and stop remaining work when it is exceeded. The proxy's own timeout is **not documented**, so report it as unverified.

## Contract and rule changes

**Request:** `POST /analyze-media`, `multipart/form-data` with fields `question` (text) and `file`. Handle one file.

**Response** extends the facts contract:

```json
{
  "verdict": "Worth it | Skim | Rot | Can't verify",
  "source": "subtitles | speech | frames",
  "facts": [{ "text": "string", "timestamp": "mm:ss or null", "url": null }],
  "missing": ["string"],
  "meta": { "tokens_in": 0, "tokens_out": 0, "frames_sent": 0 }
}
```

`source`, a nullable `timestamp`, and `url: null` are new. Errors use the existing friendly JSON `message` format.

**Exceptions to `AGENTS.md` (update it in the same change):**
1. Product rule 2 ("verify quotes"): on the frame path there are no quotes. Facts are verified against the sent frame timestamps, labelled as coming from frames, and the verdict is capped at `Skim`. Rules 1 and 3 still apply.
2. Product rule 4 ("no scraping") is unchanged. This feature only processes files the user uploads.

## Frontend

- Add the tab to `config/tabs.js` after Instagram: label "Other", path `/other`, enabled, page `OtherPage`.
- New context per the one-context-per-concern rule:

| Hook | Holds | Actions |
|---|---|---|
| `useOther()` | `question`, `file`, `status`, `result`, `error` | `setQuestion`, `setFile` (validates), `analyze()`, `reset()` |

- Guarded hook, memoized value, no JSX or fetch inside the context. Add `analyzeMedia(formData)` to `src/api.js`. It must **not** set a JSON `Content-Type`, so the browser sets the multipart boundary.
- Provider order: `... > AnalysisProvider > CompareProvider > OtherProvider > Layout`.
- `components/other/MediaForm.jsx`: question field, a native labelled `<input type="file" accept=".mp4,.mp3,video/mp4,audio/mpeg">`, the chosen file name and size, a submit button with a loading state. Built from existing primitives.
- Client-side check before upload: allowed type and `file.size` at most `MAX_UPLOAD_MB`. Show a friendly inline error and block the request. This is what actually protects the upload stream.
- One short privacy line near the form: "Files are processed on the server and deleted afterwards. Audio or frames may be sent to an AI provider."
- Result: reuse the facts panel. When `source === "frames"`, show a `Badge` labelled "From frames". Facts with a null timestamp render without a link.
- Loading: disable the form and show the `Spinner` with a status label. Keep any status text to one short line.
- Design system rules apply: tokens only, keyboard operable, visible focus, light and dark themes. Document any new component in `docs/design-system.md`.

## About page update

In `config/about.js` and its tests:
- Change the "Private by default" description to: `No accounts, no cookies. Uploaded files are deleted after processing.`
- Add a limits line: `The Other tab accepts MP4 and MP3 files up to a size and length cap.`

## Tests

Backend (pytest; mock STT, the vision API, and YouTube; no live network). Tests that need a real ffmpeg binary use `skipif` when it is missing.
- `validate`: magic-byte detection for MP4 and MP3; a wrong extension with the right content passes; a disguised other file is rejected; size and duration caps.
- `ffmpeg_runner`: asserts `shell=False`, list arguments, `-nostdin`, `-protocol_whitelist file`, and the timeout; the uploaded filename never reaches the command.
- `frames`: dedupe with synthetic Pillow images (identical frames collapse, different frames survive); evenly spaced capping; timestamp calculation.
- Frame verifier: a fact with an unknown timestamp is dropped.
- Verdict mapping: the frame path never returns `Worth it`; 0 facts gives `Rot`; MP3 with STT off gives `Can't verify`.
- Route: wrong type, too large, too long, busy (second concurrent request), `ffmpeg_unavailable`, and cleanup of the temp directory on success and on exception.
- Frontend (Vitest): client file validation (type and size) and the context guard error outside its provider.

## Docs

- `docs/adr/ADR-009-media-upload-and-frame-fallback.md`: decision, options (frames versus provider-native video input, client versus server resize, subprocess versus a Python ffmpeg binding), trade-offs, consequences, action items. Record why the verdict is capped on the frame path.
- Update `AGENTS.md` (contract, env vars, the exception), `docs/architecture.md`, and `docs/design-system.md`.

## Definition of done

- [ ] Only MP4 and MP3 are accepted, decided by content; everything else gets a friendly error
- [ ] The browser blocks oversize files before upload, and the server enforces the same cap
- [ ] The subtitle path works; STT is feature flagged and fails over cleanly
- [ ] The frame path sends one vision call with at most `MAX_FRAMES` deduplicated, mid-resolution images
- [ ] Frame results are labelled "From frames" and never return `Worth it`
- [ ] `ffmpeg_runner.py` is the only place that spawns processes, with all the rules above
- [ ] The temp directory is deleted on every path, and only one media job runs at a time
- [ ] Output is facts only, with no paragraphs
- [ ] About copy updated; no secrets committed
- [ ] ADR-009, `AGENTS.md`, `architecture.md`, and design-system docs updated
- [ ] `pytest -q`, Vitest, and `npm run build` pass
- [ ] Summary lists what changed and what was **not verified**: ffmpeg availability on Embarko, the proxy request timeout, BazaarLink STT support, and the chosen vision model's image limits