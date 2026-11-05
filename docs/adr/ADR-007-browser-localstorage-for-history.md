# ADR-007: Browser localStorage for analysis history

## Status

Accepted

## Date

2026-11-05

## Context

WorthRot has no user accounts, and users asked to revisit their previous
analysis results. History should be useful without introducing sign-in,
server-side ownership, or additional hosting state. The repository rule that
core analysis must not depend on localStorage remains satisfied: storage is
optional and analysis continues when it is blocked.

## Decision

Save successful `Worth it`, `Skim`, and `Rot` results in the user's browser
under the versioned `worthrot:history:v1` localStorage key. Keep at most 50
entries, newest first, and replace duplicates with the same video ID and
normalized question. Store only the UUID, timestamp, question, video ID, source
URL, verdict, verified facts, and missing topics. Validate data whenever it is
loaded. Never set cookies or send history to the server.

## Options

- Cookies: rejected because they are small and automatically sent with
  requests.
- IndexedDB: deferred because the small history does not need its complexity.
- Server-side history: deferred because ownership would require accounts or
  another identity mechanism.
- Browser localStorage: selected for simple, client-only storage.

## Trade-offs

History is limited to the browser and device where it was created. It is not
synced across browsers and is lost if the user clears site data. Browser
storage may be blocked or full; in that case, analysis continues and the
current session remains usable, but history cannot be saved.

## Consequences

- A context owns history actions and autosaves successful analyses.
- The History page can expand or delete results without an API or model call.
- The shared facts panel keeps the saved and live result presentations
  consistent.
- Transcripts, internal verification quotes, API keys, and token metadata are
  never stored in history.
- The server-side SQLite cache remains independent of user history.

## Action Items

- Keep entry validation, storage failures, deduplication, and history actions
  covered by offline tests.
- Keep history capped at 50 entries and handle storage events across tabs.
- Revisit storage only if account-based sync becomes a product requirement.
