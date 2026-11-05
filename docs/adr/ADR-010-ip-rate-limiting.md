# ADR-010: IP-based daily request limits

## Status

Accepted

## Date

2026-11-05

## Context

The application has no accounts and the shared model API is billable. A limit
is needed to control provider spend and protect the memory-constrained host,
while keeping the three analysis features available without sign-up.

IP-based limits are approximate, not a hard guarantee:

| Limitation | Effect | Mitigation |
|---|---|---|
| Embarko proxies requests | `request.remote_addr` may be the proxy, putting users in one bucket | Select the configured trusted X-Forwarded-For hop from the right; verify the deployed behavior |
| Forwarding headers can be spoofed | A caller may try to choose a different bucket | Trust only the configured platform-added hop, never the leftmost entry |
| Shared campus, office, and carrier addresses | Many people, including judges, share one quota | Optional demo bypass key; global cap still applies |
| Rotating IPs, VPNs, and IPv6 | A determined user can evade per-IP limits | Normalize IPv6 to `/64` and enforce a global daily cap |
| IP addresses are personal data in some regions | Persisted addresses create privacy exposure | Store only a salted HMAC, purge counts older than yesterday, and disclose retention on About |

## Decision

Implement a standard-library Flask decorator for `/analyze`, `/compare`, and
`/analyze-media`. Each feature has an independent per-client limit of 10
successful requests per calendar day in `RATE_LIMIT_TZ` (default UTC).
Reserve a slot before invoking the route, then release it for any non-2xx
response or exception. Cache hits and `Can't verify` results returned with 200
count. Compare is one request for quota purposes, though it may cost up to
three LLM calls.

Store per-client and global counts in a dedicated `DATA_DIR/ratelimit.sqlite`
database. SQLite connections are thread-local with a busy timeout. A
transaction with conditional updates reserves both limits atomically. The
global daily cap is independent per feature, defaults to 200, and has
environment configuration. Storage failures fail closed with a friendly 503.

Resolve the client address from the configured `TRUSTED_PROXY_HOPS` entry
counted from the right in `X-Forwarded-For`, falling back to
`request.remote_addr` when unavailable or invalid. Key IPv4 by full address
and IPv6 by `/64`. Persist only `HMAC-SHA256(salt, normalized_ip)`. Use
`RATE_LIMIT_SALT` when configured; otherwise persist a random salt in
`DATA_DIR/rate_salt` with mode 0600. Purge old count rows at startup and on
every 100th limited request. Never log client IPs or bypass keys.

The optional `RATE_LIMIT_BYPASS_KEY` compared with `hmac.compare_digest`
skips only the per-client counter. It does not bypass the global cap.
`RATE_LIMIT_ENABLED=false` disables enforcement for local development.

Quota responses include standard `X-RateLimit-*` headers. `GET /limits`
reports each feature's available per-client quota without consuming it. The
browser shows remaining requests near each submit button and disables the
button at zero; server enforcement remains authoritative.

The real forwarding-header behavior and trusted hop count on Embarko are
unverified. The application logs only the number of forwarded hops once at
DEBUG level. Persistence of `DATA_DIR` across host restarts and redeploys, and
provider-side spend limits, also remain unverified.

## Options

- **Flask-Limiter with in-memory storage:** rejected because counters reset on
  restart and do not coordinate reliably across workers.
- **Redis:** rejected because it adds a service and hosting dependency.
- **Custom SQLite storage:** selected because it is already available in the
  standard library and can persist beneath `DATA_DIR`; immediate transactions
  serialize concurrent reservations.
- **Client-side `localStorage` counters:** rejected because callers can clear
  or edit them.
- **CAPTCHA:** rejected because it adds friction and does not provide a direct,
  predictable spend ceiling.

## Trade-offs

- A proxy misconfiguration may group all users together or use an unintended
  hop; the deployed header chain must be verified.
- Shared addresses share a quota. Rotating addresses can evade a per-client
  cap, so the global cap is necessary.
- SQLite contention can add latency. A busy timeout and separate database
  limit cache interference; storage errors fail closed.
- The default global cap is an initial budget guard and must be tuned against
  actual provider costs.
- IP-derived hashes remain linkable personal data while the salt and rows
  exist. Salted hashing and short retention reduce, but do not eliminate, that
  privacy risk.

## Consequences

- Every limited request reserves before request-body parsing or expensive
  processing, then releases quota on validation, media, LLM, and server
  failures.
- A `429` identifies per-feature exhaustion (`rate_limited`) or global service
  capacity (`capacity_reached`) and reports the next local reset time.
- `/limits` and the frontend RateLimit context keep quota status visible; the
  browser convenience never replaces server-side checks.
- Compare remains one request in the quota while its actual LLM cost can be
  up to three analyses.
- About and repository documentation disclose the hashed-IP retention period.

## Action Items

- Verify the actual client-IP forwarding chain and trusted hop count on
  Embarko before relying on per-network fairness.
- Confirm `DATA_DIR` survives restarts and redeploys.
- Set a provider-side spend limit and tune `GLOBAL_DAILY_CAP_PER_FEATURE`
  against measured costs.
- Revisit the 10-per-feature limit and 200 global cap after observing usage.
