# ADR-013: Multilingual evidence and retrieval

## Status

Accepted

## Date

2026-11-07

## Context

The analyzer's English-only caption selection and lexical retrieval limited
video checks to English, while exact quote verification and timestamps must
remain reliable across languages. Users also need results in the language of
their question when the source transcript uses a different language.

## Decision

This decision supersedes ADR-006 where its single-call limit or English-only
caption behavior conflicts with multilingual caption selection and the
retrieval-only question translation described here.

Select YouTube captions using the detected question language and caption-track
type, retaining both selected and original language codes and a source label.
When a long transcript and question use different languages, an optional
retrieval-only model request translates the question into the transcript
language. Short transcripts skip that request. Translation failure does not
block analysis; the result records the failure and continues with best-effort
retrieval.

Use NFKC normalization, case folding, script-aware tokenization and limits, and
selected invisible-control removal for quote verification. Preserve ZWJ and
ZWNJ. Facts and missing items are requested in the question language; internal
quotes remain copied from the original transcript and must verify against its
timestamped windows before becoming public facts.

Persist language/source metadata with cached results and browser History
summaries, but never persist transcripts or uploads in browser History. Report
transcript language/source in video and media results. Language detection is
heuristic when upstream metadata is unavailable and is not a promise of
complete support for every language.

## Options

- **Translate the full transcript:** rejected because it adds cost and risks
  changing the evidence used for quote verification.
- **Translate the question only for retrieval:** selected to preserve original
  timestamped evidence and exact quotes.
- **Require translation success:** rejected; best-effort retrieval preserves
  the existing no-evidence fallback behavior.
- **Add a language-detection dependency:** rejected in favor of lightweight
  script and stopword heuristics and provider language codes.

## Trade-offs

- One additional model request may be used for long cross-language analyses.
- Script-aware retrieval improves matching for scripts without word spaces but
  does not replace evaluation on real multilingual videos.
- Heuristic Latin-language detection can be uncertain, especially for short
  questions; source-provided language codes take precedence for transcripts.
- Machine-generated and translated captions may be less reliable and are
  labeled in result metadata.

## Consequences

- Analyze and media result metadata includes question/transcript language and
  transcript source; Analyze also reports original transcript language and
  whether retrieval translation failed.
- Compare exposes per-video metadata and the detected question language.
- Facts still require verified timestamped quotes, and translation output is
  never accepted as evidence.
- The frontend marks multilingual content with language and automatic text
  direction attributes and displays transcript source information.
- Existing cache and History entries without language metadata remain valid.

## Action Items

- Keep script tokenization, quote normalization, caption selection, translation
  fallback, and language metadata covered by offline tests.
- Evaluate verified-fact rate and timestamp accuracy on multilingual examples
  before claiming broad language support.
- Keep the API contract, models, frontend labels, and architecture
  documentation synchronized as language metadata evolves.
