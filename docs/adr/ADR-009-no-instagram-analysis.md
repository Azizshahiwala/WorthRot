# ADR-009: Keep WorthRot focused on YouTube analysis

## Status

Accepted

## Date

2026-11-05

## Context

Instagram analysis was considered as a future feature, with pasted transcripts
as its proposed input. The product is now focused on analyzing YouTube videos
and comparing YouTube sources for a question. Keeping an Instagram tab or
placeholder implies planned support that is no longer intended.

## Decision

Do not offer Instagram analysis. Remove its placeholder page and navigation
entry. WorthRot supports YouTube URLs and user-pasted timestamped transcripts
for single-video analysis; Compare accepts YouTube URLs only.

## Options

- Keep a disabled Instagram tab as a future placeholder.
- Remove Instagram from the product and keep a YouTube-only source scope.

The YouTube-only scope is selected to keep the interface and product
expectations aligned with implemented functionality.

## Trade-offs

- Users cannot begin an Instagram workflow or infer that it is coming soon.
- Any future non-YouTube source requires a new product decision, source-specific
  validation, and updated tests and documentation.

## Consequences

- The navbar no longer has an Instagram entry or route.
- No Instagram ingestion, scraping, or media download behavior is supported.
- Product and agent documentation describe YouTube-only video sources.

## Action Items

- Keep source links and documentation YouTube-only.
- Revisit non-YouTube analysis only with an explicit future product decision.
