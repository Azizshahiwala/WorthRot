# NEXT_INSTRUCTIONS.md: UI foundation (design system, navbar, context)

Read `AGENTS.md` first. This file adds to it and does not replace it. If the two conflict on a hard constraint (hosting, product rules), `AGENTS.md` wins.

## Goal

Build the frontend foundation: a design system, a navbar, a modular context-based architecture, and placeholder tabs. **Only the YouTube feature is functional.** Everything else is a placeholder.

## Scope

**In scope**
1. Design system (tokens, base components, documented in `docs/design-system.md`)
2. Navbar with tabs
3. Context-based state management (clean `useContext` usage)
4. YouTube analyzer page as the default page, implemented in `App()`
5. Placeholder pages for future tabs
6. Flask catch-all so client-side routes work on Embarko

**Out of scope (do not build yet)**
- Instagram, comparison/ranking, history, or auth logic
- Any new backend endpoint beyond the existing `/analyze` and `/health`
- Animations beyond simple hover/focus transitions

## Navigation structure

| Tab | Route | Status | Page component |
|---|---|---|---|
| YouTube (default) | `/` | **Functional** | `App()` |
| Compare | `/compare` | Placeholder | `ComparePage` |
| Instagram | `/instagram` | Placeholder | `InstagramPage` |
| History | `/history` | Placeholder | `HistoryPage` |
| About | `/about` | Placeholder | `AboutPage` |

- `App()` is the first and default page: it renders the YouTube analyzer at `/`.
- The navbar and providers live in a layout wrapper, not inside `App()`.
- Tabs are defined once in a config array (`src/config/tabs.js`). The navbar renders from it. Adding a tab must not require editing `NavBar.jsx`.
- Placeholder pages render one shared `<ComingSoon title="..." />` component. Do not duplicate markup.

## Routing

- Use `react-router-dom` v6 (the one new dependency; justified because nested layout routes and active-link handling are needed).
- Use `BrowserRouter`.
- **Flask must serve `frontend/dist/index.html` for any non-API path** (catch-all route registered after `/analyze` and `/health`). Otherwise a refresh on `/compare` returns 404 on Embarko.
- API paths stay un-prefixed as in `AGENTS.md`. The catch-all must not shadow them.

## Context architecture (no spaghetti)

Rules:
1. **One context per concern.** No single global "AppContext" holding everything.
2. **Each context lives in its own file with three exports:** the Provider, a custom hook (`useX`), and nothing else. Components never call `useContext(XContext)` directly. They call the hook.
3. **The hook throws a clear error** if used outside its provider.
4. **Contexts hold state and actions only.** No JSX, no styling, no fetch calls inline. API calls go through `src/api.js`.
5. **Memoize** context values (`useMemo`, `useCallback`) to avoid needless re-renders.
6. **Components stay dumb.** Page components compose hooks and presentational components. Logic lives in hooks and contexts.
7. No prop drilling beyond one level where a context exists.

Contexts to create:

| Context | Hook | Holds | Actions |
|---|---|---|---|
| `AnalysisContext` | `useAnalysis()` | `question`, `url`, `transcript`, `status` (`idle`/`loading`/`success`/`error`), `result`, `error` | `setQuestion`, `setUrl`, `setTranscript`, `analyze()`, `reset()` |
| `ThemeContext` | `useTheme()` | `theme` (`light`/`dark`) | `toggleTheme()` |
| `ToastContext` | `useToast()` | toast queue | `showToast(message, type)` |

`NavContext` is **not** needed: active tab state comes from the router.

Provider order in `main.jsx`: `BrowserRouter` > `ThemeProvider` > `ToastProvider` > `AnalysisProvider` > `Layout`.

## Folder structure to create

```
frontend/src/
├── main.jsx                    # providers + router, nothing else
├── App.jsx                     # default page: YouTube analyzer (route "/")
├── api.js                      # fetch wrapper for /analyze
├── config/
│   └── tabs.js                 # tab definitions (label, path, element, enabled)
├── contexts/
│   ├── AnalysisContext.jsx
│   ├── ThemeContext.jsx
│   └── ToastContext.jsx
├── hooks/
│   └── (one file per hook only if logic is shared beyond a context)
├── layout/
│   ├── Layout.jsx              # NavBar + <Outlet /> + Toast host
│   └── NavBar.jsx
├── pages/
│   ├── ComparePage.jsx
│   ├── InstagramPage.jsx
│   ├── HistoryPage.jsx
│   └── AboutPage.jsx
├── components/
│   ├── ui/                     # design system primitives
│   │   ├── Button.jsx
│   │   ├── Input.jsx
│   │   ├── Textarea.jsx
│   │   ├── Card.jsx
│   │   ├── Badge.jsx           # verdict badge variants
│   │   ├── Spinner.jsx
│   │   └── Toast.jsx
│   ├── ComingSoon.jsx
│   └── youtube/
│       ├── QuestionForm.jsx
│       ├── VerdictCard.jsx
│       └── EvidenceList.jsx
└── styles/
    ├── tokens.css              # all design tokens as CSS variables
    ├── base.css                # reset, typography, focus styles
    └── components.css          # or CSS modules per component
```

Naming: components `PascalCase.jsx`, hooks `useX`, contexts `XContext.jsx`, CSS classes `kebab-case`. One component per file.

## Design system

Follow the `/design-system` skill structure: tokens, components (variants, states, sizes, accessibility), patterns. Document the result in `docs/design-system.md` using that skill's "Document" format for every component in `components/ui/`.

**Principle:** consistency over creativity. No hardcoded colors, spacing, or font sizes in components. Always use a token.

### Tokens (`styles/tokens.css`)

Define as CSS variables on `:root`, and override under `[data-theme="dark"]`.

| Category | Tokens |
|---|---|
| Color: brand | `--color-brand`, `--color-brand-hover`, `--color-brand-contrast` |
| Color: neutral | `--color-bg`, `--color-surface`, `--color-border`, `--color-text`, `--color-text-muted` |
| Color: semantic (verdicts) | `--color-worth` (green), `--color-skim` (amber), `--color-rot` (red), `--color-unverified` (grey), plus a `-bg` tint for each |
| Color: feedback | `--color-success`, `--color-warning`, `--color-danger`, `--color-info` |
| Typography | `--font-sans`, `--font-mono`; scale `--text-xs` to `--text-2xl`; weights `--weight-regular/medium/bold`; `--leading-tight/normal` |
| Spacing | 4px base: `--space-1` (4) to `--space-8` (64) |
| Radius | `--radius-sm`, `--radius-md`, `--radius-lg`, `--radius-full` |
| Shadow | `--shadow-1`, `--shadow-2` |
| Motion | `--duration-fast` (120ms), `--duration-base` (200ms), `--ease-standard` |
| Layout | `--nav-height`, `--content-max-width` |

Pick a calm, readable palette. All text and verdict colors must meet WCAG AA contrast (4.5:1 for body text) in both themes. Verify and note the ratios in `docs/design-system.md`.

### Components (`components/ui/`)

| Component | Variants | States | Sizes |
|---|---|---|---|
| Button | primary, secondary, ghost | default, hover, active, focus-visible, disabled, loading | sm, md, lg |
| Input / Textarea | default, error | default, focus, disabled, error | md |
| Card | default, elevated | default | n/a |
| Badge | worth, skim, rot, unverified | default | sm, md |
| Spinner | n/a | n/a | sm, md |
| Toast | success, error, info | enter, exit | n/a |

Every interactive component needs:
- Visible `:focus-visible` outline using a token
- Keyboard operability
- Correct semantic element (`<button>`, `<nav>`, `<label>`)
- A disabled/loading state that blocks repeat clicks

### Navbar spec

- Semantic `<nav aria-label="Main">` with a list of links rendered from `config/tabs.js`.
- Active tab uses `NavLink` and `aria-current="page"` with a clear visual indicator (not color alone).
- Placeholder tabs are navigable but show a small "Soon" badge.
- Contains the product name "WorthRot" (links to `/`) and a theme toggle button (`aria-label` set, shows current mode).
- Responsive: below 640px, tabs collapse into a menu button with a keyboard-accessible dropdown (Escape closes it).
- Sticky at the top, height `--nav-height`.

### Patterns to document

- **Form pattern:** label, input, helper/error text, submit button with loading state (used by `QuestionForm`).
- **Feedback pattern:** toast for transient messages, inline error for validation.
- **Data display pattern:** verdict card with badge, confidence, evidence list with clickable timestamp links.

## YouTube page behavior (`App()`)

1. `App()` composes `QuestionForm` and the result area using `useAnalysis()`. No fetch or business logic inside `App()`.
2. Inputs: question (required), YouTube URL, optional pasted transcript (collapsed by default, labelled as the fallback).
3. On submit, `analyze()` calls `api.js` which posts to `/analyze` using the contract in `AGENTS.md`.
4. Render states: idle (short helper text), loading (spinner and disabled form), success (`VerdictCard`), error (inline message plus toast).
5. `VerdictCard` shows: verdict badge, confidence, evidence list (quote plus timestamp link), and the "missing" list.
6. Honor the product rules in `AGENTS.md` (evidence required, no guessing, friendly errors).

## Docs to produce

- `docs/design-system.md`: tokens table, each `ui/` component documented (description, variants, props, states, accessibility, do/don't, code example), the three patterns, and the contrast check results.
- `docs/adr/ADR-005-react-context-per-concern-and-router.md`: decision to use one context per concern plus `react-router-dom` with a Flask catch-all. Include options considered (single global context, Redux/Zustand, tab state without a router) and trade-offs.
- Update `docs/architecture.md` with the frontend structure and provider order.

## Definition of done

- [ ] `/` shows the YouTube analyzer; every other tab shows the shared `ComingSoon` page
- [ ] Refreshing on `/compare` works on the Flask server (catch-all verified)
- [ ] No component calls `useContext` directly; every context has a hook that throws outside its provider
- [ ] No hardcoded colors, spacing, or font sizes outside `tokens.css`
- [ ] Navbar is keyboard-navigable with a visible focus state, and has the mobile collapse
- [ ] Light and dark themes both pass AA contrast
- [ ] `docs/design-system.md`, ADR-005, and `architecture.md` updates are written
- [ ] `pytest -q` and `npm run build` pass
- [ ] Summary lists what was changed and what was not verified