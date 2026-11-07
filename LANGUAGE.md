# WorthRot: Multi-Language Support (Video and Audio)

## Goal
Let users check videos, subtitles and uploaded audio/video in languages other than English, with the same guarantees as today: **every fact is backed by a verified quote and a timestamp**.

Two rules protect quality:
1. **Quotes stay in the original language.** Verification remains an exact text match against the real transcript.
2. **Facts and gap lines are written in the question's language**, so the user can read the answer.

## What blocks other languages today

| Area | Today | File |
| --- | --- | --- |
| YouTube captions | Only `languages=["en"]`; errors say "No English captions" | `transcript.py` |
| Retrieval | `\w+` tokens work for spaced languages, but stopwords are English only; Chinese, Japanese, Thai have no spaces, so a whole sentence becomes one token | `retriever.py` |
| Question and video in different languages | No lexical overlap, so nothing is retrieved | `retriever.py` |
| Context size | `estimate_tokens` = chars / 4; underestimates Indic, CJK, Arabic | `retriever.py` |
| Word limits | Facts ≤ 15 words and quotes ≤ 12 words counted with `split()`; meaningless without spaces | `verdict.py`, `vision.py` |
| Quote matching | `casefold` + whitespace only; misses Unicode form differences (full-width characters, composed vs decomposed accents) | `verifier.py` |
| Speech-to-text | No language hint, no detected language kept | `media/stt.py` |
| Embedded subtitles | Takes the stream index with no language choice | `media/subtitles.py` |
| Prompts | English only | `prompts/verdict_prompt.txt`, `media/vision.py` |

## Design

### 1. Language detection and metadata
- Detect the question language and the transcript language (short, dependency-light detector, or the language code the source already provides).
- Return in `meta`: `questionLanguage`, `transcriptLanguage`, `transcriptSource` (`manual`, `auto`, `translated`, `speech`, `subtitles`).
- Include language and source in the cache key, plus a prompt version.

### 2. YouTube caption selection (`transcript.py`)
Replace the fixed English fetch with `YouTubeTranscriptApi().list(video_id)` and choose in this order:
1. Manual captions in the question's language.
2. Manual captions in the video's original language.
3. Auto-generated captions in the original language.
4. Any translatable track translated to the question's language (`translate(code)`), labelled **translated**.

Prefer the original language over YouTube's machine translation whenever the pipeline can handle it (see section 3). Replace "English captions" errors with "No usable captions were found."

### 3. Question and transcript in different languages
- When the languages differ, make one small LLM call that translates the **question** into the transcript language, used only for retrieval. Windows from the real transcript are still what is sent to the model and quoted.
- Short transcripts that already fit the context are sent whole, so no translation is needed.
- Prompt additions: "Write `f` and `missing` in the question's language. Copy `q` exactly from the transcript in its original language. Never translate quotes."
- If the translation call fails, fall back to sending the best-effort windows and flag the result as lower confidence.

### 4. Tokenization and retrieval (`retriever.py`)
- Normalize with NFKC, then `casefold`.
- Spaced scripts: `\w+` tokens with small stopword lists per language (start with Hindi, Gujarati, Spanish, French, German, Portuguese, Arabic). Stopwords are optional per language.
- No-space scripts (Chinese, Japanese, Thai, Lao, Khmer, Burmese): character bigrams as tokens.
- Accent-insensitive matching for Latin scripts only. Never strip combining marks in Indic scripts or Arabic, because they change meaning.

### 5. Limits that depend on script
- Word counter: for no-space scripts count about one word per 2 characters; keep `split()` elsewhere.
- Token estimate: per-script characters-per-token constants (Latin about 4; Indic, Arabic and CJK lower). Treat the constants as tunable and validate against real model usage numbers.

### 6. Verification (`verifier.py`)
- Normalize quote and window with NFKC + `casefold` + whitespace collapse.
- Remove only invisible characters that never matter (BOM, zero-width space, bidi control marks). **Keep ZWJ and ZWNJ**, which carry meaning in Indic and Persian text.
- The timestamp logic from the earlier fix works unchanged because it matches normalized text to caption lines.

### 7. Audio and uploaded files (`media/stt.py`)
- Optional `language` field on the upload form, default **Auto-detect**.
- ElevenLabs: pass the language code when given; keep the detected code from its response.
- Gemini: instruct "Transcribe verbatim in the original language(s) and script. Do not translate. Keep code-switching (for example Hindi and English mixed) as spoken."
- Keep the detected language in the result `meta`.
- Check each provider's current supported-language list before publishing the dropdown; do not promise languages the providers do not list.

### 8. Embedded subtitles (`media/subtitles.py`)
- Read each stream's language tag (ffprobe) and pick: question language, then original language, then first stream.
- Report which stream was used.

### 9. Frames and on-screen text (`media/vision.py`)
- Prompt: "Read on-screen text in any language. Report facts in the question's language."
- Mark frame-based facts from small or stylized non-Latin text as approximate.

### 10. Frontend
- Show a small line on each result: `Transcript: Hindi, auto-generated` or `Translated from Spanish`.
- Add `lang` and `dir="auto"` to fact and quote text so right-to-left text renders correctly.
- Add a font stack with Noto fallbacks for Indic, Arabic and CJK glyphs.
- Optional "Video language" select on the Other tab (Auto-detect default).
- Interface translation (menus, buttons) is a separate later phase; this spec covers content only.

## Rollout

| Phase | Scope | Why first |
| --- | --- | --- |
| 1 | Caption selection, metadata, error text, `dir`/`lang` | Unlocks non-English YouTube videos |
| 2 | Tokenizer, normalization, verifier, script-aware limits | Needed for accurate retrieval and verification |
| 3 | Cross-language question translation | Lets an English question check a Hindi video and the reverse |
| 4 | STT language hint and detection, subtitle stream choice, vision prompt | Audio and uploads |
| 5 | Interface translation | Optional polish |

## Tests
- Unit tests: tokenizer per script, NFKC and ZWJ/ZWNJ handling in the verifier, caption track selection with mocked track lists (manual, auto, translated, none), script-aware word counter.
- Fixtures: one short transcript each in Hindi, Gujarati, Spanish, Japanese and Arabic.
- Evaluation set: about 10 videos per language with known answers. Track **verified-fact rate** and **timestamp error in seconds**, and compare with English.
- Acceptance: no verified fact whose quote is absent from the transcript, in any language.

## Risks
- Auto-generated and machine-translated captions are noisier; the UI labels them so users can judge.
- Model quality is uneven in low-resource languages; the evaluation set decides which ones to list as supported.
- The translation call adds a small cost per cross-language request.
- Script-aware token and word limits need measuring on real outputs, not assumed.
EOF