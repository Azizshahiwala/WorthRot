# INSTRUCTIONS_ABOUT.md: About tab

Read `AGENTS.md` and `NEXT_INSTRUCTIONS.md` first. This file adds to them. If it conflicts with a hard constraint or product rule in `AGENTS.md`, `AGENTS.md` wins.

## Goal

Replace the About placeholder with a short, static page that explains what WorthRot is, how it works, and its limits. The tone matches the product: short, factual, no hype, no long paragraphs.

## Scope

**In scope**
1. A functional `AboutPage` at `/about`
2. Content stored as data in `src/config/about.js`
3. Small presentational components
4. Enabling the tab in the navbar config

**Out of scope**
- Any backend change or API call
- Any context, state, or storage (the page is static, so it needs **no** context)
- Analytics, contact forms, blog, changelog, or team pages

## Files

```
frontend/src/
├── config/
│   └── about.js              # all copy and links (single source of truth)
├── pages/
│   └── AboutPage.jsx         # composes sections; no copy hardcoded here
└── components/about/
    ├── AboutSection.jsx      # heading + children, one per section
    ├── StepList.jsx          # numbered steps
    └── PrincipleList.jsx     # short title + one-line description items
```

One component per file. Components only render the data passed in. In `config/tabs.js`, mark About as enabled and remove its "Soon" badge. Remove the `ComingSoon` usage for this route.

## Content (put in `config/about.js`)

Keep every line short. Use this copy as written, and flag anything you change.

**Hero**
- Title: `Is this video worth your time?`
- Subtitle: `Ask a question. Get facts from the video, with timestamps.`

**How it works** (ordered steps)
1. `Ask` : `Enter your question and a YouTube link.`
2. `Check` : `We read the captions and find the parts that match.`
3. `Verify` : `Every fact is checked against the transcript before you see it.`

**Principles**
- `Facts only` : `Short answers with timestamps. No summaries.`
- `Verified` : `Facts that can't be found in the transcript are dropped.`
- `No guessing` : `If the video doesn't answer it, we say so.`
- `Private by default` : `History stays in your browser. No accounts, no cookies.`

**Limits** (be honest, keep short)
- `Works with YouTube videos that have captions.`
- `Results are only as good as the transcript.`
- `Instagram is not read directly. Paste support is planned.`
- `WorthRot can make mistakes. Check the video if it matters.`

**Built with**
- `Flask, React, and Claude. Hosted on Embarko. Built for the Embarko AI hackathon.`

**Author block (placeholders, the owner fills these in)**
- `name`, `role`, `githubUrl`, `projectRepoUrl` as empty strings in `about.js` with a comment saying so.
- Render the block **only** for fields that are non-empty. Never invent a name or a link.

## UI rules

- Semantic structure: one `<h1>` (hero title), `<h2>` per section, `<ol>` for steps, `<ul>` for principles and limits.
- Use only existing tokens and `components/ui/` primitives (`Card`, `Badge` if needed). No hardcoded colors, spacing, or font sizes.
- Content width capped by `--content-max-width`, readable line length, comfortable spacing from the spacing scale.
- External links: `target="_blank"` with `rel="noopener noreferrer"`, and visible link styling with a focus ring. Make the link text descriptive (for example "WorthRot on GitHub").
- Works in light and dark themes and at mobile widths. Keyboard navigable, no color-only meaning.
- No images or animation required. If you add an icon, it must be decorative (`aria-hidden`).
- Do not add helper paragraphs beyond the copy above.

## Tests

Add a Vitest test for the data module (no new dependency beyond what History set up):
- `about.js` exports every required key (hero, steps, principles, limits, builtWith).
- Steps are exactly 3 and numbered in order.
- No empty strings in required copy fields.
- Author link fields are either empty or valid `https://` URLs.

## Docs

- Update `docs/architecture.md`: About is a static page driven by `config/about.js`, with no context or API.
- Update `docs/design-system.md` only if you add a new reusable component or pattern.
- No ADR needed.

## Definition of done

- [ ] `/about` shows the full page, and the tab no longer shows "Soon"
- [ ] All copy lives in `config/about.js`; no copy hardcoded in components
- [ ] No context, API call, or storage added
- [ ] Author block hides when its fields are empty
- [ ] Semantic headings and lists; keyboard-navigable with visible focus
- [ ] Correct in light and dark themes and on mobile widths
- [ ] No hardcoded colors, spacing, or font sizes
- [ ] Vitest data tests pass, plus `npm run build`
- [ ] Summary lists what changed, which copy was edited, and what was not verified