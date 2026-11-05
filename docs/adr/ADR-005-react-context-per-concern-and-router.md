# ADR-005: React context per concern and client-side routing

## Status

Accepted

## Date

2026-11-04

## Context

The frontend needs shared analysis form state, theme selection, and transient
notifications, as well as navigable placeholder pages. Client-side routes must
continue to load when refreshed on the Flask-hosted frontend.

## Decision

Use one React context per concern (`AnalysisContext`, `ThemeContext`,
`ToastContext`, and `HistoryContext`), each with a provider and guarded custom hook. Use
`react-router-dom` v6 with `BrowserRouter`, a shared layout route, and a
configuration-driven tab list. Flask serves the built `index.html` for
non-API paths so browser refreshes resolve client-side routes.

Providers are nested in this order: `BrowserRouter`, `ThemeProvider`,
`ToastProvider`, `HistoryProvider`, `AnalysisProvider`, and the layout.

## Options

- A single global context for all shared state.
- Redux or Zustand for shared state management.
- Tab selection without a router.

## Trade-offs

Separate contexts keep state ownership focused and avoid updates unrelated
consumers do not need, at the cost of a few small provider files. React Router
adds one dependency, but supplies nested layout routes and active-link
semantics; a hand-built tab state would need to recreate URL handling,
navigation, and refresh behavior. Flask's fallback is necessary for direct
navigation and refreshes on a browser-history router.

The required v6 dependency currently triggers two moderate `npm audit`
advisories; npm suggests a breaking upgrade to v7. Keep the requested v6
version and static, internal navigation targets for this scaffold. Reassess
before accepting untrusted route destinations or adding server-side rendering.

## Consequences

Components consume context through the matching hook, which throws when used
outside its provider. The navigation list is maintained in one configuration
file. Unknown client-side paths redirect to `/`, and the API routes retain
priority over Flask's frontend fallback.

## Action Items

- Keep new tabs in `src/config/tabs.js` and use the shared placeholder for
  unfinished pages.
- Add analysis behavior only through the existing API contract and
  `src/api.js`.
- Preserve `/analyze` and `/health` when changing the Flask fallback.
