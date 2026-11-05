# ADR-011: Save Other result summaries in browser History

## Status

Accepted

## Date

2026-11-05

## Context

Users need to revisit completed analyses of their uploaded MP4 and MP3 files.
The existing History feature is browser-local and stores a sanitized analysis
summary, while media uploads and extracted transcripts must remain temporary.

## Decision

Save every completed `/analyze-media` result supported by the History verdict
schema (`Worth it`, `Skim`, `Rot`, or `Can't verify`) through the existing
`HistoryProvider`. Mark these entries as `media` and display them as
`Other upload`. Preserve nullable media timestamps by normalizing missing
timestamps and URLs to empty strings in the History summary. Do not retain the
uploaded file, original filename, transcript, provider metadata, or internal
quotes. Keep Compare results out of History.

Media entries are not deduplicated because no upload identifier is retained;
separate completed uploads remain separate entries.

## Options

- **Store the upload or its filename:** rejected because it retains user media
  or potentially identifying metadata.
- **Do not store Other results:** rejected because users cannot revisit their
  completed upload analysis from History.
- **Store only the result summary:** selected to match existing browser-local
  History while respecting temporary-upload privacy.

## Trade-offs

- History records that an analysis came from an Other upload but cannot
  identify or reopen the original file.
- Distinct uploads with the same question are separate entries.
- Browser storage limits and user-cleared site data still apply.

## Consequences

- `OtherProvider` writes completed results through `HistoryProvider`.
- History validation supports media source labels and `Can't verify` verdicts.
- History stores no uploaded media or transcript content.
- History UI identifies media entries as `Other upload`.

## Action Items

- Keep History tests, `AGENTS.md`, `INSTRUCTIONS_OTHER.md`, and
  `docs/architecture.md` aligned with this rule.
- Continue to exclude Compare results, uploaded files, and transcripts from
  browser History.
