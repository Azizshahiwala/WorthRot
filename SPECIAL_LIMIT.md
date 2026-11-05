# SPECIAL_LIMIT.md: daily request cap per feature, keyed by IP

Read `AGENTS.md` (including the appended addendum) and `NEXT_INSTRUCTIONS.md` first. This file adds to them. If it conflicts with a hard constraint or product rule in `AGENTS.md`, `AGENTS.md` wins. The contract additions below are intentional, and you must update `AGENTS.md` to match.

## Goal

Cap usage without user accounts: each client IP may make **10 successful requests per day, per feature**. The cap protects LLM spend and the 256 MB host.

Features and their counters:

| Feature key | Route |
|---|---|
| `analyze` | `POST /analyze` |
| `compare` | `POST /compare` |
| `media` | `POST /analyze-media` |

History, About, `/health` are not limited. Each feature has its own counter, so one IP can make up to 10 requests on each feature per day.

## Known limitations (read first, record in ADR-010)

IP-based limiting is **approximate**, not a hard guarantee.

| Limitation | Effect | Mitigation in this design |
|---|---|---|
| Embarko runs the app behind a proxy | `request.remote_addr` may be the proxy's IP, which would put **every user in one bucket** | Read the client IP from `X-Forwarded-For` with a trusted hop count (see below). Verify on the deployed app. |
| Spoofable forwarding header | A caller could send their own `X-Forwarded-For` to dodge the cap | Trust only the entry added by the platform proxy (count from the right), never the leftmost value |
| Shared IPs (campus, office, mobile carriers) | Many real people share one quota, including **judges** | Optional demo bypass key (below) |
| Rotating IPs, VPNs, IPv6 | A determined person can exceed the cap | Group IPv6 by `/64`; add a **global daily cap** per feature as a cost ceiling |
| IP addresses are personal data in some regions | Privacy exposure | Store only a salted hash, keep it for at most 2 days, and say so on the About page |

## Rules

1. **Count only successful requests.** Reserve a slot when the request starts (this prevents concurrent overshoot) and **release it** if the response is not `2xx`. Validation errors (400, 413, 415, 422), `busy`, `ffmpeg_unavailable`, and LLM or server failures never consume quota.
2. Cache hits **do** count. `Can't verify` results returned with `200` also count.
3. `/compare` counts as **one** request regardless of how many videos it contains (note the extra cost in ADR-010).
4. The check runs **before** any LLM call, ffmpeg call, or request body parsing. For `/analyze-media`, do not touch `request.files`, `request.form`, or `request.get_json()` until the limit check has passed.
5. The limiter must **fail closed**: if storage errors, return a friendly `503` for limited routes and log it. Do not let requests through uncounted.
6. A day is one calendar day in `RATE_LIMIT_TZ` (default `UTC`, which resets at 05:30 IST). Use the standard library `zoneinfo`.

## Client IP resolution (`backend/rate_limit.py`)

- Read `X-Forwarded-For`, split on commas, and take the entry that is `TRUSTED_PROXY_HOPS` from the **right** (default `1`). If the header is missing, fall back to `request.remote_addr`.
- Validate with `ipaddress`. If parsing fails, fall back to `remote_addr`.
- IPv4: key on the full address. IPv6: key on the `/64` prefix.
- The key is `HMAC-SHA256(salt, normalized_ip)`. Never store, log, or return a raw IP.
- Salt: `RATE_LIMIT_SALT` env var. If empty, generate a random salt once and persist it in `DATA_DIR/rate_salt` (create with mode `0600`), so hashes stay stable across restarts.
- **The real header behavior on Embarko is unverified.** Log only the number of forwarded hops once at DEBUG level on the first request. Do not log IP values in production. Report this as not verified in the summary.

## Storage

A separate SQLite file `DATA_DIR/ratelimit.sqlite` (avoids lock contention with the cache database). One connection per thread, with a busy timeout.

```
rate_counts(key_hash TEXT, feature TEXT, day TEXT, count INTEGER, PRIMARY KEY (key_hash, feature, day))
global_counts(feature TEXT, day TEXT, count INTEGER, PRIMARY KEY (feature, day))
```

- **Atomic reserve:** upsert the row, then increment only while `count < limit` using a single conditional `UPDATE` and check `rowcount`. Two concurrent requests must never both take the last slot. Do the same for the global counter.
- **Release:** decrement (never below 0) when a reserved request ends non-`2xx`.
- **Purge:** delete rows with a `day` older than yesterday at process start and on every 100th request. No timers or background libraries.
- `day` is stored as `YYYY-MM-DD` in `RATE_LIMIT_TZ`.

## Enforcement

Implement a decorator, for example `@limited("analyze")`, applied to the three routes. It:
1. Resolves the key, then reserves a per-IP slot and a global slot (release the first if the second fails).
2. On denial, returns `429` (see below) without running the view.
3. Runs the view; on a non-`2xx` result or an uncaught exception, releases the slots.
4. Adds the headers below to every limited response.

**Demo bypass (optional):** if `RATE_LIMIT_BYPASS_KEY` is set and the request carries a matching `X-Demo-Key` header (compare with `hmac.compare_digest`), skip the per-IP limit. The global cap still applies. This is for judges and shared networks. Never log the key.

**Disable switch:** `RATE_LIMIT_ENABLED=false` turns everything off for local development.

## Contract additions

Headers on every limited response (success or `429`):

```
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 7
X-RateLimit-Reset: <epoch seconds of the next reset>
```

`429` body (also sets `Retry-After`):

```json
{ "message": "Daily limit reached for this feature. It resets at the time shown.", "code": "rate_limited",
  "retry_after_seconds": 12345, "resets_at": "ISO 8601" }
```

When the global cap is hit, use `code: "capacity_reached"` and a message saying the service is at capacity for today.

New endpoint `GET /limits` (does not consume quota, not itself limited):

```json
{ "limits": {
    "analyze": { "limit": 10, "remaining": 10, "resetsAt": "ISO 8601" },
    "compare": { "limit": 10, "remaining": 10, "resetsAt": "ISO 8601" },
    "media":   { "limit": 10, "remaining": 10, "resetsAt": "ISO 8601" } } }
```

## Config (add to `.env.example`)

```
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_FEATURE=10
RATE_LIMIT_ANALYZE=
RATE_LIMIT_COMPARE=
RATE_LIMIT_MEDIA=
GLOBAL_DAILY_CAP_PER_FEATURE=200
RATE_LIMIT_TZ=UTC
TRUSTED_PROXY_HOPS=1
RATE_LIMIT_SALT=
RATE_LIMIT_BYPASS_KEY=
```

Per-feature overrides, when set, replace `RATE_LIMIT_PER_FEATURE` for that feature. The global cap default is a starting value to tune against your API budget. Never hardcode secrets.

## Frontend (follow the design system and context rules)

- New context `RateLimitContext` with a guarded `useRateLimit()` hook. It holds `limits` per feature (`limit`, `remaining`, `resetsAt`) and exposes `refresh()` and `update(feature, rate)`. It calls `GET /limits` once on mount through `src/api.js`.
- Provider order: `... > HistoryProvider > RateLimitProvider > AnalysisProvider > CompareProvider > OtherProvider > Layout`.
- `src/api.js` returns the parsed rate headers with each response. Each feature context passes them to `update(feature, rate)` after a call. Only the feature contexts do this, and nothing else writes to the rate limit context.
- On `429`: show an inline message and a toast (`useToast()`), and set `remaining` to 0 for that feature.
- New component `components/ui/` or `components/` `RateLimitNotice.jsx`, placed under the submit button on the YouTube, Compare, and Other forms:
  - Normal: one muted line, "7 of 10 left today".
  - Zero: the submit button is disabled and the line reads "Daily limit reached. Resets at <local time>." This also stops a large media upload from being sent when it would be refused.
  - Polite live region; tokens only; light and dark themes.
- The server remains the authority. The disabled button is a convenience, not enforcement.

## About page update

In `config/about.js` and its tests:
- Add to limits: `Each feature allows 10 requests per day per network.`
- Change the privacy line to: `No accounts, no cookies. A hashed IP is kept for up to 2 days to enforce the daily limit. Uploaded files are deleted after processing.`

## Tests

Backend (pytest; inject a fake clock; no live network):
- **Atomicity:** 20 concurrent requests against a limit of 10 allow exactly 10.
- **Release rules:** non-`2xx` responses and exceptions release the slot; `2xx` responses keep it.
- **Per-feature independence**, **day rollover** (clock change resets counts), and the **global cap** (returns `capacity_reached`).
- **IP handling:** IPv6 addresses in the same `/64` share a key; with `X-Forwarded-For: 1.2.3.4, 5.6.7.8` and 1 hop, the key comes from `5.6.7.8`, so a spoofed leftmost value does not help; invalid values fall back to `remote_addr`; raw IPs never appear in the database or logs.
- **Salt:** persisted and stable across a simulated restart.
- **Bypass key:** correct key skips the per-IP limit, wrong or missing key does not, the global cap still applies.
- **Disabled flag**, **fail closed** when storage raises, and **purge** of old rows.
- **Responses:** `429` shape and headers; `/limits` does not consume quota; the check runs before the body is parsed on `/analyze-media`.

Frontend (Vitest): rate header parsing, notice states (normal, zero, unknown), and the context guard error outside its provider.

## Docs

- `docs/adr/ADR-010-ip-rate-limiting.md`: decision, options (Flask-Limiter with in-memory storage, Redis, custom SQLite, client-side counters in `localStorage` which are trivially bypassed, CAPTCHA), trade-offs, consequences, and the limitations table above. Record that Compare counts as one request but costs up to three LLM calls.
- Update `AGENTS.md` (contract: headers, `429`, `/limits`; env vars; privacy note), `docs/architecture.md`, and `docs/design-system.md` (the notice component).

## Definition of done

- [ ] Each feature rejects the 11th successful request from one client per day with a correct `429`
- [ ] Failed or invalid requests do not use up quota
- [ ] Limit check runs before body parsing, LLM, and ffmpeg work
- [ ] Concurrent requests cannot exceed the cap
- [ ] No raw IPs are stored, logged, or returned; hashed entries are purged after about 2 days
- [ ] Global daily cap works and returns `capacity_reached`
- [ ] UI shows remaining requests and disables submit at zero; `429` is handled gracefully
- [ ] About copy updated, `.env.example` updated, no secrets committed
- [ ] ADR-010, `AGENTS.md`, and `architecture.md` updated
- [ ] `pytest -q`, Vitest, and `npm run build` pass
- [ ] Summary lists what was **not verified**: the real client-IP header and hop count on Embarko, whether `DATA_DIR` persists across restarts and redeploys, and any provider-side spend limit