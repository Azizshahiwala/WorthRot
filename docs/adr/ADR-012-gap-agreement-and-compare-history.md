# ADR-012: Question gaps, cross-video agreement, and Compare History

## Status

Accepted

## Date

2026-11-07

## Context

Users need a concise view of which parts of their question the checked facts
cover, and where verified facts across compared videos agree or conflict.
Compare previously had no grouped History entry, while ADR-008 described
per-video Compare History behavior that was not present in the implementation.

## Decision

Add an optional question-part `gap` summary to single-video and media results.
Generate it in the existing fact extraction request (including the existing
frame-analysis request), then cap `covered` parts by the number of verified
facts. No verified facts forces every part to `missing`. Results with no parts
or older cache entries without `gap` remain valid and hide the panel.

After deterministic ranking, make one short, deadline-bounded agreement request
only when at least two videos have verified facts. Supply only the question and
those verified facts. Return `agree`, `disagree`, and `unanswered` summaries;
exclude unrecognized video labels. Agreement failure never fails Compare, and
does not change `best` or ranking.

Save each completed Compare request as one browser History entry containing the
ranked verified facts and optional agreement. Preserve temporary-media privacy:
History never stores uploads, transcripts, internal quotes, or provider token
metadata. This supersedes ADR-008's History persistence details.

## Options

- **Use the existing fact-extraction call for question gaps:** selected to avoid
  an additional provider request for YouTube and transcript-based media.
- **Compare full transcripts for agreement:** rejected because agreement must
  describe only already-verified facts and would add unnecessary input.
- **Make agreement mandatory for Compare success:** rejected so an optional
  provider failure cannot break deterministic ranking.
- **Save each Compare video as a separate History row:** rejected in favor of a
  single grouped entry that preserves the comparison context and agreement.

## Trade-offs

- Gap labels are model-produced and describe checked evidence only; capping
  covered parts by verified-fact count is conservative but cannot establish
  one-to-one fact support for each part.
- Agreement adds one provider call and some cost when at least two videos have
  verified facts. It uses a short timeout within the Compare deadline.
- Browser History may consume more space for Compare entries because it keeps
  multiple verified fact lists, but the existing entry-count cap remains.
- Existing cache entries without gap data continue to work and display no gap
  panel until reanalyzed.

## Consequences

- `/analyze`, `/analyze-media`, and per-video Compare results expose optional
  `gap` data; Compare also exposes nullable `agreement` and includes its usage
  in aggregate token totals.
- The shared FactsPanel displays gap summaries for fresh results and History.
- Compare History stores the question, ranking, facts, optional gap, and
  agreement as one validated summary.
- Ranking order and `best` remain controlled by the existing code ranker.

## Action Items

- Keep API models, prompts, frontend response validators, History validation,
  tests, `AGENTS.md`, and `docs/architecture.md` aligned.
- Mock provider calls in tests and cover missing/invalid gap data, evidence
  caps, invalid agreement labels, provider failure, and History round-trips.
- Rebuild the frontend before deployment and include both prompt files in the
  deployment package.
