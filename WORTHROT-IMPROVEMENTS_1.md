# WorthRot: Two Improvements

1. **Knowledge Gap Detector**: which parts of the question are covered, which are missing.
2. **Cross-Video Agreement**: where 2–3 compared videos agree, disagree, or leave questions open.

Both are **additive**. Existing verdict, facts and `missing` output stay unchanged. Each new result sits in a light shaded block beneath the existing output.

---

## 1. Knowledge Gap Detector

### Behaviour
- Splits the user's question into 2–4 short parts and marks each **covered / partial / missing**.
- Adds one extra verdict line in a light shaded area under the current result, in every feature that produces a verdict (YouTube, Other/media upload, each video in Compare, History view).
- Existing `missing` list stays. The gap line is the question-level summary; `missing` is the video-level list.

Example:

> *Verdict: Skim* (existing)
> *Facts…* (existing)
> ░ **Gap check: 2 of 3 parts covered.** ✅ Cost of setup · ✅ Required tools · ❌ Maintenance time ░

### Backend

**Prompt (`backend/prompts/verdict_prompt.txt`)**: extend the JSON by one optional field. This reuses the existing LLM call, so there is no extra request or cost beyond a few tokens.

```json
"parts":[{"p":"question part, at most 8 words","s":"covered|partial|missing"}]
```
Rules to add: at most 4 parts; judge each part only from the transcript windows; `covered` needs supporting text in a window.

**`backend/services/verdict.py`**
- `parse_model_json`: parse `parts` if present, validate (length, word limit, `s` in allowed set). If absent or invalid, return `parts: []`. Never raise, so old behaviour is unaffected.
- Add `map_gap(parts, verified_fact_count)`:
  - `verified_fact_count == 0` → every part forced to `missing` (stops the model claiming coverage with no verified evidence).
  - Otherwise cap the `covered` count at `verified_fact_count`.
  - Returns `{"covered": n, "total": n, "label": "All covered | Partly covered | Not covered", "parts": [...]}`.

**`backend/models.py`**: add `GapPart` and `GapCheck` TypedDicts; add `gap: GapCheck | None` to `AnalysisResponse` and `MediaAnalysisResponse`.

**`backend/services/analyzer.py`, `backend/services/media/analyzer.py`, `backend/services/pipeline.py`**: attach `gap` to the result. In `_failure_result` set `gap: None`.

**`backend/routes/compare.py`**: include `gap` in `_public_video_result`.

**Cache**: results are cached per (video id, question hash). Old cached entries have no `gap`. Either bump a cache/prompt version in `backend/cache.py` so they refresh, or let the UI hide the block when `gap` is missing (do at least the latter).

### Frontend
- New `frontend/src/components/ui/GapCheck.jsx`: shaded block (`background` from a light CSS variable, with dark-mode value), one summary line, then part chips with ✅ / ◐ / ❌ **plus text labels** (not colour only).
- Render it inside `FactsPanel.jsx` after the facts and missing list, so YouTube, Other, Compare and History all get it automatically.
- Render nothing if `result.gap` is null or `parts` is empty.
- Store `gap` in the History entry so old and new entries both render.

### Acceptance
- A question with 3 parts, 2 answered, shows "2 of 3 parts covered" with the missing part named.
- A transcript with zero verified facts shows "Not covered".
- Old cached result with no `gap` shows the existing UI only, with no error.

---

## 2. Cross-Video Agreement

### Behaviour
- In the **Compare tab**, after ranking, show one extra shaded text block with three lines:
  - **Agree:** points two or more videos support.
  - **Disagree:** points where videos give different answers, with each position.
  - **Unanswered:** parts of the question that no video covers.
- Appears below the rank table and per-video results. Existing ranking and "best" pick are untouched.
- Based on the **verified facts** already extracted, so it states what the checked facts show, not what the videos might say elsewhere.

Example:

> ░ **Agree:** Video A and C both say you need a 12V supply.
> **Disagree:** A says setup takes 10 min; B says about an hour.
> **Unanswered:** None of the videos covers warranty. ░

### Backend

**New prompt `backend/prompts/agreement_prompt.txt`**
- Input: the question, and for each video a label (A/B/C) with its numbered verified facts (fact text + timestamp). No transcripts, so the call is small and cheap.
- Output JSON only:
```json
{"agree":[{"point":"≤15 words","videos":["A","C"]}],
 "disagree":[{"point":"≤12 words","positions":[{"video":"A","claim":"≤10 words"}]}],
 "unanswered":["≤8 words"]}
```
- Rules: use only the supplied facts; do not infer; differences in detail are not a disagreement unless the facts conflict; max 3 items per list.

**New `backend/services/agreement.py`**
- `build_agreement(settings, question, ranked_results) -> dict | None`.
- Skip and return `None` when fewer than 2 videos have verified facts (nothing to compare).
- Reuse the request/parse helpers from `verdict.py` (factor `_request_facts` to accept a prompt filename).
- Validation: drop any item referencing a video label that doesn't exist; `agree` items need 2+ videos; `disagree` items need 2+ positions.
- Wrap in try/except. On any LLM or parse error return `None` so **Compare never fails because of this feature**.

**`backend/routes/compare.py`**
- After `rank_results`, call `build_agreement(...)` and add `"agreement": {...} | null` to the response.
- Add its token usage to `meta.tokens_in_total / tokens_out_total`.
- Same request, so the existing `compare` rate limit applies. Respect `compare_timeout_seconds` with a short timeout for this call.

### Frontend
- New `frontend/src/components/compare/AgreementBlock.jsx`: shaded block with the three labelled lines. Show video letters with their rank/ID so the reader can map A/B/C to the cards.
- Render in `ComparePage.jsx` between `RankTable` and `CompareResultList`.
- Hide the block when `agreement` is null. If a list is empty, show a plain line such as "No clear disagreements found".
- Add `agreement` to the `api.js` compare response handling and to the History entry for Compare.

### Acceptance
- Two videos with overlapping facts show at least one **Agree** line naming both.
- Conflicting facts produce a **Disagree** line with both positions.
- If an agreement call fails, the Compare page still shows the ranking normally.
- Compare with one failed video and one good video shows no agreement block.

---

## Shared notes

- **Honest limits.** Each video yields at most 5 facts, so both features describe the *checked facts*, not the whole video. Word the UI accordingly.
- **Cost.** Gap Detector adds a few output tokens to an existing call. Agreement adds one small call per Compare.
- **Tests (`tests/`).** Add parser tests for `parts` (valid, invalid, missing), `map_gap` rules, agreement validation (bad labels, single-video input), and a Compare route test where the agreement call raises.
- **Rollout order.** Gap Detector first (smaller), then Agreement.
- **Redeploy.** Rebuild with `npm run build`, repackage `worthrot-deploy.zip` (include `frontend/dist` and the new prompt file), and deploy with a new version label.