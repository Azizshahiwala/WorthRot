# WorthRot: Improvements Log

## 1. Timestamp accuracy

**Problem:** A fact's timestamp was the start of a ~40 s transcript window, not where the quote was said, so links could land up to ~40 s early.

| Change | Where |
| --- | --- |
| Windows now keep their caption segments (`segments`, optional, default empty) | `models.py`, `chunker.py` |
| Retriever copies windows with `dataclasses.replace`, so segments survive scoring and clipping | `retriever.py` |
| Timestamp = start of the caption line where the quote begins (falls back to window start if no segments) | `verifier.py` |
| Video link starts 2 s before the fact (`LINK_LEAD_IN_SECONDS`, never below 0); the displayed time stays exact | `analyzer.py` |

**Tests added:** quote located in the correct caption line (`test_verifier.py`); link lead-in and zero floor (`test_analyze.py`). Backend: 105 passed. Frontend: 47 passed.

**Not changed:** captions that are themselves off (auto-caption lag), pasted transcripts from a different cut, and speech-to-text drift on uploaded files. Results cached before this update keep their old window-start times until the cache is cleared or the entry is refreshed.

## 2. UI: text symbols replaced with icons

React has no built-in emoji or icon library, so icons now come from `lucide-react` (`^0.453.0`).

| Old symbol | Icon | File |
| --- | --- | --- |
| x (close/dismiss) | `X` | `Toast.jsx`, `HistoryItem.jsx`, `NavBar.jsx` |
| menu glyph | `Menu` | `NavBar.jsx` |
| moon / sun glyphs | `Moon` / `Sun` | `NavBar.jsx` |
| right arrow | `ArrowRight` | `QuestionForm.jsx` |

Icons are decorative (`aria-hidden`); buttons keep their existing text labels. Typographic punctuation (apostrophes, ellipses, dashes) is unchanged.

## 3. Planned, not yet built

See `worthrot-improvements.md`: Knowledge Gap Detector and Cross-Video Agreement.

## Deploy notes
- Rebuilt `frontend/dist` (JS 285 KB, gzip 89 KB). Upload `worthrot-deploy.zip` with a new version label.
- `lucide-react` is bundled into `dist`, so the server needs nothing new.