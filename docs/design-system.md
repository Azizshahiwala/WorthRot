# WorthRot design system

The interface uses a maximalist video-store/zine direction: tomato red,
cobalt, lemon, warm paper, condensed display type, and high-contrast inked
edges. Components use CSS custom properties from
`frontend/src/styles/tokens.css`; new data-display styles use shared color,
spacing, and typography tokens.

## Tokens

| Category | Tokens | Use |
|---|---|---|
| Brand colors | `--color-brand`, `--color-brand-hover`, `--color-brand-contrast`, `--color-brand-text` | Brand surfaces, accessible text contrast, and emphasis |
| Neutral colors | `--color-bg`, `--color-surface`, `--color-border`, `--color-text`, `--color-text-muted` | Page, cards, borders, and text |
| Verdict colors | `--color-worth`, `--color-skim`, `--color-rot`, `--color-unverified` and their `-bg` pairs | Verdict badges and evidence |
| Feedback colors | `--color-success`, `--color-warning`, `--color-danger`, `--color-info` | Toasts and inline feedback |
| Typography | `--font-sans`, `--font-mono`, `--text-xs` through `--text-2xl`, `--weight-regular/medium/bold`, `--leading-tight/normal`, `--tracking-*` | Text roles and hierarchy |
| Spacing | `--space-1` through `--space-8` | Padding, margin, and gaps (4px base) |
| Shape and depth | `--radius-sm/md/lg/full`, `--shadow-1/2` | Corners and elevation |
| Motion | `--duration-fast`, `--duration-base`, `--ease-standard` | Hover and focus transitions |
| Layout and controls | `--nav-height`, `--content-max-width`, `--control-height`, `--focus-ring-width`, `--border-width`, `--min-app-width`, and semantic `--*-width`/`--*-height` tokens | Shared layout and interactive sizing |

`[data-theme="dark"]` overrides color tokens only. Theme choice is held in
`ThemeContext` for the current page session and applied to the root element.

## Components

### Button

- **Description:** Semantic button for actions and form submission.
- **Variants:** `primary`, `secondary`, `ghost`.
- **Sizes:** `sm`, `md`, `lg`.
- **Props:** Standard button props, `variant`, `size`, `loading`, `disabled`,
  and `className`.
- **States:** Default, hover, active, focus-visible, disabled, and loading.
- **Accessibility:** Uses `<button>`, preserves keyboard activation, exposes
  `aria-busy`, and disables repeat activation while loading. Focus uses the
  global visible focus ring.
- **Do:** Set `type="submit"` for form submission and provide an accessible
  name.
- **Don't:** Use a styled `<div>` as an action.
- **Example:** `<Button variant="primary" size="lg" loading>Analyze</Button>`

### Input

- **Description:** Labelled single-line text input.
- **Variants:** Default and error (`error` prop).
- **Sizes:** `md`.
- **Props:** Native input props, `id`, required `label`, `hint`, `error`, and
  `className`.
- **States:** Default, focus, disabled, and error.
- **Accessibility:** Associates a visible `<label>` with the input and links
  hint/error copy using `aria-describedby`; sets `aria-invalid` for errors.
- **Do:** Use a descriptive label and explain validation errors.
- **Don't:** Depend on placeholder text as the only label.
- **Example:** `<Input label="Your question" name="question" required />`

### Textarea

- **Description:** Labelled multi-line text entry for pasted transcripts.
- **Variants:** Default and error (`error` prop).
- **Sizes:** `md`.
- **Props:** Native textarea props, `id`, required `label`, `hint`, `error`, and
  `className`.
- **States:** Default, focus, disabled, and error.
- **Accessibility:** Uses a visible associated label, hint/error description,
  and `aria-invalid`.
- **Do:** Keep the transcript optional and explain its purpose.
- **Don't:** Use it for short single-line values.
- **Example:** `<Textarea label="Video transcript" rows={6} />`

### Card

- **Description:** Surface for grouping related content.
- **Variants:** `default`, `elevated`.
- **Sizes:** Not applicable.
- **Props:** `variant`, `className`, children, and standard `div` props.
- **States:** Static.
- **Accessibility:** Neutral `<div>`; use a heading and a meaningful landmark
  when the card represents a section.
- **Do:** Use elevation sparingly to distinguish a result from its form.
- **Don't:** Put interactive content inside a card without preserving the
  controls' semantics.
- **Example:** `<Card variant="elevated">Result content</Card>`

### Badge

- **Description:** Compact text indicator for a verdict or availability.
- **Variants:** `worth`, `skim`, `rot`, `unverified`.
- **Sizes:** `sm`, `md`.
- **Props:** `variant`, `size`, and optional children.
- **States:** Static.
- **Accessibility:** Includes a text label so verdict meaning is not conveyed
  by color alone.
- **Do:** Use the matching verdict variant and keep its text visible.
- **Don't:** Use color as the only indicator.
- **Example:** `<Badge variant="worth">Worth it</Badge>`

### Spinner

- **Description:** Small decorative progress indicator with an accessible
  status label.
- **Variants:** None.
- **Sizes:** `sm`, `md`.
- **Props:** `size`, `label`.
- **States:** Indeterminate loading.
- **Accessibility:** Exposes `role="status"` and visually hidden label text.
- **Do:** Pair it with text describing the current operation.
- **Don't:** Use it as the only feedback for a long-running operation.
- **Example:** `<Spinner size="md" label="Analyzing video" />`

### Toast

- **Description:** Dismissible transient notification.
- **Variants:** `success`, `error`, `info`.
- **Sizes:** Not applicable.
- **Props:** `id`, `message`, `type`, `onDismiss`.
- **States:** Entered, visible, dismissing, and dismissed.
- **Accessibility:** Error messages use `role="alert"`; other messages use
  `role="status"`. The dismiss button has an accessible name.
- **Do:** Use to supplement persistent inline errors.
- **Don't:** Put essential instructions only in a toast.
- **Example:** `<Toast message="Saved" type="info" onDismiss={dismissToast} />`

## Patterns

### Form

`QuestionForm` uses a visible label, helper text, optional transcript fallback,
context validation, and a submit button that disables during loading.
Validation and request failures remain visible in the result region and are
also announced as toasts.

### Feedback

Use inline errors for actionable validation and request failures. Use toasts
for short-lived supplemental feedback. The analysis result area uses polite
live announcements; errors use alert semantics.

### Data display

`VerdictCard` is a compact facts panel. It places the text verdict badge before
a short bulleted list; each line pairs one verified fact with its timestamp
link. Transcript-only facts show a timestamp without a link. Missing topics
appear as muted chips only when present. There are no confidence scores, quote
blocks, summaries, or explanatory paragraphs in the success result. In
development only, a muted metadata line shows input/output token usage and a
cache tag for cached results.

## Contrast verification

Ratios below use the WCAG relative-luminance calculation on the foreground and
background token pairs. WCAG AA requires at least 4.5:1 for normal text.

| Theme | Foreground / background | Contrast |
|---|---|---:|
| Light | `--color-text` / `--color-bg` | 14.87:1 |
| Light | `--color-text-muted` / `--color-bg` | 7.55:1 |
| Light | `--color-text-muted` / `--color-surface` | 8.40:1 |
| Light | `--color-text` / `--color-surface` | 16.54:1 |
| Light | `--color-brand-text` / `--color-surface` | 6.92:1 |
| Light | `--color-brand-contrast` / `--color-brand` | 4.69:1 |
| Light | Button text / primary button | 11.76:1 |
| Light | Worth / worth tint | 5.61:1 |
| Light | Skim / skim tint | 5.65:1 |
| Light | Rot / rot tint | 5.18:1 |
| Light | Unverified / unverified tint | 8.41:1 |
| Light | Empty-state text / blue surface | 7.27:1 |
| Dark | `--color-text` / `--color-bg` | 16.31:1 |
| Dark | `--color-text-muted` / `--color-bg` | 10.40:1 |
| Dark | `--color-text-muted` / `--color-surface` | 9.25:1 |
| Dark | `--color-text` / `--color-surface` | 14.50:1 |
| Dark | `--color-brand-text` / `--color-surface` | 7.06:1 |
| Dark | `--color-brand-contrast` / `--color-brand` | 6.56:1 |
| Dark | Worth / worth tint | 7.76:1 |
| Dark | Skim / skim tint | 8.15:1 |
| Dark | Rot / rot tint | 6.24:1 |
| Dark | Unverified / unverified tint | 8.26:1 |
| Dark | Empty-state text / blue surface | 4.94:1 |

All listed text pairs exceed the 4.5:1 normal-text threshold.
