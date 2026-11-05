# INSTRUCTIONS_HISTORY.md: History tab with browser storage

Read `AGENTS.md`, `NEXT_INSTRUCTIONS.md`, and `INSTRUCTIONS_FACTS_PIPELINE.md` first. This file adds to them. If it conflicts with a hard constraint or product rule in `AGENTS.md`, `AGENTS.md` wins.

## Goal

The app has no user accounts. Save each successful analysis in the user's own browser and show it in the **History** tab. No backend changes, no database, no login.

## Decision: localStorage, not cookies

| Option | Verdict | Reason |
|---|---|---|
| `localStorage` | **Use this** | About 5 MB, client-only, simple API, not sent to the server |
| Cookies | Do not use | About 4 KB limit, sent with every request (wasteful), meant for server-readable state |
| IndexedDB | Not now | Overkill for about 50 small entries |
| Server-side history | Not now | Needs accounts or identifiers, and adds hosting state |

The app must set **no cookies**. Record this in ADR-007.

## Scope

**In scope**
1. A storage module with safe read and write
2. `HistoryContext` plus `useHistory()` hook
3. Auto-saving every successful analysis
4. A functional History tab (list, view, delete one, clear all)
5. Enabling the tab in the navbar config

**Out of scope**
- Sync across devices or browsers
- Export or import, sharing, search, tags
- Storing transcripts, API keys, or anything but the result data below
- Persisting the in-progress form or theme

## What to store

Only save **successful** results (a verdict was produced). Do not save errors or `Can't verify` caused by failures.

Entry shape:

```json
{
  "id": "uuid",
  "createdAt": "ISO 8601 string",
  "question": "string",
  "videoId": "string",
  "url": "string",
  "verdict": "Worth it | Skim | Rot",
  "facts": [{ "text": "string", "timestamp": "mm:ss", "url": "string" }],
  "missing": ["string"]
}
```

- Never store the transcript, the internal verification quotes, or `meta` token counts.
- Use `crypto.randomUUID()` with a simple fallback.
- Storage envelope under the key `worthrot:history:v1`:

```json
{ "version": 1, "entries": [ ... newest first ... ] }
```

## Storage module (`src/lib/historyStorage.js`)

Pure functions, no React, no JSX. Exports:

| Function | Behavior |
|---|---|
| `loadHistory()` | Reads and parses. On missing key, bad JSON, or wrong shape, returns `[]`. Drops individual entries that fail validation. Runs `migrate()` if the version is older. |
| `saveHistory(entries)` | Writes the envelope. Returns `{ ok: true }` or `{ ok: false, reason }`. |
| `validateEntry(entry)` | Returns true only if every required field has the right type. |
| `migrate(envelope)` | Stub that upgrades older versions. Today it only passes version 1 through. |

Rules:
- Wrap **every** `localStorage` access in `try/catch`. Storage can be disabled (private mode, blocked) or full. The app must still work with history unavailable.
- On `QuotaExceededError`: drop the oldest entries, retry once, then report failure.
- Cap at `MAX_HISTORY_ENTRIES = 50` (constant in one place). Drop the oldest beyond the cap.
- Never trust stored data. Treat it as untrusted input and validate on every load.

## Context (`src/contexts/HistoryContext.jsx`)

Follow the context rules in `NEXT_INSTRUCTIONS.md`: provider plus a guarded hook, no direct `useContext` in components, memoized value.

| Hook | Holds | Actions |
|---|---|---|
| `useHistory()` | `entries`, `available` (false if storage is blocked) | `addEntry({ question, videoId, url, result })`, `removeEntry(id)`, `clearHistory()` |

Behavior:
- Initialize state from `loadHistory()` once.
- `addEntry` builds the entry, **replaces any existing entry with the same `videoId` and normalized question** (lowercased, trimmed, collapsed whitespace), puts the new one first, applies the cap, then saves.
- After every change, persist through `saveHistory`. If it fails, set `available` to false and show a toast through `useToast()`. Keep the in-memory list working for the session.
- Listen to the `storage` event so a second open tab stays in sync. Clean up the listener on unmount.

Provider order in `main.jsx` becomes:
`BrowserRouter` > `ThemeProvider` > `ToastProvider` > `HistoryProvider` > `AnalysisProvider` > `Layout`

`AnalysisProvider` calls `addEntry` inside its `analyze()` success path, in one place only. No other component writes to history.

## History tab UI (`src/pages/HistoryPage.jsx`)

Replace the `ComingSoon` placeholder. In `config/tabs.js`, mark History as enabled and remove its "Soon" badge.

Layout and states:
- **List:** newest first. Each row shows the question (truncated to one line), the verdict `Badge`, the date, and the video URL host or ID.
- **View an entry:** expand the row in place to show the facts and missing items using the **same facts panel component** as the YouTube page. Viewing must **not** call the API or the LLM.
- **Delete one:** icon button per row with an accessible name (for example "Delete analysis: <question>").
- **Clear all:** a secondary button with a two-step inline confirm (first click changes the label to "Confirm clear all", second click clears; resets after a few seconds or on blur). Announce the result in a live region.
- **Empty state:** one short line pointing to the YouTube tab.
- **Storage unavailable:** one short inline notice that history can't be saved in this browser.
- One short muted line on the page: "Saved on this device only."
- Use only existing tokens and `components/ui/` primitives. Keyboard operable, visible focus, semantic list (`<ul>`/`<li>`), the expand control as a `<button>` with `aria-expanded`.

Add components only if needed (`components/history/HistoryList.jsx`, `HistoryItem.jsx`). One component per file. Any new UI primitive must be documented in `docs/design-system.md`.

## Privacy

- Data stays in the user's browser and is never sent to the server.
- Questions are user-typed text. Do not log or transmit history.
- Do not store sensitive data beyond the entry shape above.

## Tests

Add Vitest as a dev dependency (justify it in the commit message: no frontend test runner exists yet). Test the pure logic:
- `historyStorage`: load with missing key, corrupt JSON, wrong shape, and mixed valid and invalid entries; save success; quota failure path (mock `localStorage` to throw); cap enforcement; `validateEntry`.
- Dedupe: the same video and normalized question replaces the old entry and moves to the top.
- `addEntry` and `removeEntry` ordering, and `clearHistory` result.
- Hook throws a clear error when used outside the provider.

Do not call the network in tests.

## Docs

- `docs/adr/ADR-007-browser-localstorage-for-history.md`: decision, options (cookies, IndexedDB, server-side), trade-offs (per-browser only, lost when the user clears site data, no cross-device sync), consequences, action items.
- Update `docs/architecture.md` with the new context, provider order, and storage module.
- Update `docs/design-system.md` with the History list pattern and any new component.

## Definition of done

- [ ] A successful analysis appears in History after a page refresh
- [ ] Same video and question never creates duplicates
- [ ] View, delete one, and clear all work; viewing makes no API call
- [ ] Corrupt or blocked storage does not break the app
- [ ] The app sets no cookies
- [ ] Capped at 50 entries; the oldest are dropped
- [ ] Keyboard-navigable with visible focus; light and dark themes both look correct
- [ ] No hardcoded colors, spacing, or font sizes
- [ ] ADR-007 and docs updated
- [ ] Vitest tests pass, plus `pytest -q` and `npm run build`
- [ ] Summary lists what changed and what was not verified