# 10 · Security and privacy

v1 is public and anonymous (D18), and the Worker pays for every model call with Settle's keys. So the main risks are spend abuse and key exposure, then the usual web risks. Every control below has a test or a check in `12-deployment-and-operations.md`.

## Threat model

| # | Threat | Main controls |
|---|---|---|
| T1 | Key leaks (repo, bundle, logs, responses) | Keys only as Worker secrets; nothing secret in `vars` or `VITE_*`; gitleaks in CI; `dist/` scan; upstream bodies never forwarded |
| T2 | Bots or scripts burn the budget (denial of wallet) | Turnstile session, per-session and per-IP rate limits and daily meters, global daily and monthly budget, OpenRouter credit limit |
| T3 | Gateway used as a free general-purpose model relay | Fixed jobs with server-side prompts, schemas, model allowlist and `max_tokens`; outputs must pass Zod and invariants; meta answers capped |
| T4 | Cross-site requests use a visitor's session (CSRF) | `__Host-` cookie with `SameSite=Strict`, Origin and `Sec-Fetch-Site` checks, JSON content type required, no CORS |
| T5 | XSS steals data or drives the API | Strict CSP with Trusted Types, model text rendered as text, no third-party scripts except Turnstile |
| T6 | Prompt injection raises the ceiling or changes numbers | The engine computes every number; user text is only ever the user message |
| T7 | Malicious import file | Size cap, Zod, replay and re-hash, nothing executed |
| T8 | Supply-chain compromise | Lockfile, `minimumReleaseAge`, blocked install scripts, Dependabot, Actions pinned by SHA |
| T9 | Privacy leak through logs or telemetry | Metadata-only logs, hashed IPs with a daily salt, no message text anywhere on the server |

## Data

- Decision data stays in the user's browser (IndexedDB). There is no Settle database for decisions; the server stores only usage counters.
- What passes through the Worker per call: the user's message, the current frame and state, and the last two replies. The Worker forwards them to OpenRouter (or Jev) and keeps nothing: no message text in storage, logs, errors or analytics.
- What the Worker stores (Durable Objects): per session and per IP hash, counts and spend for the current UTC day; global spend for the day and the month. Entries expire after 48 hours (session and IP) and 40 days (global).
- Network destinations from the browser: the app's own origin, and `challenges.cloudflare.com` for Turnstile. From the Worker: OpenRouter, TypeSafe (if enabled) and Turnstile siteverify.
- Say this plainly in Settings → Privacy, including that OpenRouter routes only to providers that don't store or train on prompts (`07`, Provider preferences).
- No analytics or error reporting by default. If added later, make them opt-in and never send message text.

## Keys and secrets

- Secrets exist only as Cloudflare Worker secrets (`wrangler secret put`) and, locally, in `.dev.vars` (gitignored). List in `07`, Where calls run.
- Never in source, `wrangler.jsonc` `vars`, `VITE_*` variables, logs, error responses, exports or URLs. The browser has no key to leak.
- Separate keys per environment (development, staging, production), each with its own OpenRouter credit limit. Rotate on any suspicion; `SESSION_SECRET_PREVIOUS` lets sessions survive a rotation for 24 hours.
- CI holds one secret, `CLOUDFLARE_API_TOKEN`, scoped to "Workers Scripts: Edit" on this account only, used only by the deploy job on tags.
- Checks: gitleaks on every push and pull request; after `pnpm build`, a scan of `dist/` for `sk-or-`, `OPENROUTER`, `JEV_`, `SECRET`; a test that `wrangler.jsonc` `vars` contains none of the secret names.

## Sessions (Turnstile)

1. The app loads the Turnstile widget (invisible mode, `action: "session"`) and gets a token.
2. `POST /api/session {turnstile_token}`. The Worker calls siteverify with `TURNSTILE_SECRET_KEY` and the visitor's IP, and requires `success`, the expected `hostname` and `action`. Tokens are single use and expire after 300 s, which siteverify enforces.
3. The Worker mints a session: a random 128-bit id plus expiry, signed with HMAC-SHA-256 (`SESSION_SECRET`), set as `__Host-settle_sid` with `Secure; HttpOnly; SameSite=Strict; Path=/; Max-Age=86400`.
4. Every other `/api` call verifies the signature and expiry in constant time. An expired or missing cookie gives 401; the app repeats steps 1 to 3 once, silently.
5. Minting is itself rate limited per IP (below), so solving one challenge can't produce many sessions.

In development and tests, use Cloudflare's Turnstile test keys (always pass, always fail), set in `.dev.vars`.

## Rate limits and spend

Four layers, cheapest first. All numbers are `vars` in `wrangler.jsonc` so they can change without a code change. The defaults are a starting point; adjust them after spike S1 measures cost per turn.

| Layer | Mechanism | Default |
|---|---|---|
| 1. Burst | Workers Rate Limiting binding, keyed by session id, per job | decision and frame turns 6/min, route 20/min, meta 6/min, intuition 6/min |
| 1. Burst | Same, keyed by IP hash | session minting 5/min; all `/api` calls 60/min |
| 2. Daily allowance | `QuotaDO` per session and per IP hash, exact and serialised | session: 40 model-backed calls and $0.75 a day; IP: $2.00 a day (allows a few people behind one NAT) |
| 2. Concurrency | `QuotaDO` per session | 1 model call in flight; a second gets 429 |
| 3. Global budget | `BudgetDO` (single instance) | $5 a day and $25 a month across all users; then 503 for everyone until the period resets |
| 4. Provider | OpenRouter key credit limit (dashboard) | Production key monthly limit set at or just above the global monthly budget |

How a call is metered:
1. Before the call, reserve the worst-case cost (prompt size estimate plus `max_tokens` at the model's listed price) in the session, IP and global meters. If any would exceed its limit, refuse with 429 or 503.
2. After the call, settle each reservation to the actual `usage.cost` (and to zero if the upstream call failed before generating). Repair calls and retries reserve again.
3. Responses carry `RateLimit` and `Retry-After` headers; `GET /api/usage` tells the app what's left.

The Rate Limiting binding counts per Cloudflare location and is eventually consistent, so it only smooths bursts; the Durable Objects are the exact limits. The IP hash is `HMAC(IP_HASH_SECRET, ip + utc_date)`, so it can't be reversed or linked across days.

## Input limits

| Field | Limit |
|---|---|
| Request body | 64 KB; checked from `Content-Length` and while reading, before parsing |
| `text` / `question` | 4,000 characters |
| `frame` + `state` | 48 KB together, and must pass the Zod schemas |
| `recent` | at most 2 turn pairs, 4,000 characters each |
| `model` | must be in `MODEL_ALLOWLIST` |
| Unknown fields | rejected (`.strict()` schemas) |

## Requests (CSRF and CORS)

- `/api` accepts only `POST` (plus `GET` for `config` and `usage`) with `Content-Type: application/json`; anything else is 405 or 415.
- `Origin` must equal the app's origin, and `Sec-Fetch-Site`, when present, must be `same-origin`; otherwise 403.
- No `Access-Control-Allow-*` headers are ever sent, so other sites can't read responses.
- Cookies are `SameSite=Strict` and `__Host-` prefixed (no `Domain`, so a sibling `*.workers.dev` site can't set or read them).

## Response headers

Static assets get these from `public/_headers`; `/api` responses get them from `worker/http.ts`, plus `Cache-Control: no-store`.

```
Content-Security-Policy: default-src 'none'; script-src 'self' https://challenges.cloudflare.com; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-src https://challenges.cloudflare.com; manifest-src 'self'; worker-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'; object-src 'none'; require-trusted-types-for 'script'; trusted-types 'none'; upgrade-insecure-requests
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Content-Type-Options: nosniff
Referrer-Policy: no-referrer
Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Resource-Policy: same-origin
X-Frame-Options: DENY
```

- No `'unsafe-inline'` and no `'unsafe-eval'`. shadcn and Tailwind compile to a static stylesheet, so `style-src 'self'` works. If a component needs inline `style` attributes, allow only `style-src-attr 'unsafe-inline'`, never for scripts.
- Trusted Types: check in P0.4 that Turnstile works with it enforced. If it doesn't, ship `require-trusted-types-for` in `Content-Security-Policy-Report-Only` and log the decision in `11`.
- The whole `.dev` top-level domain is on the browsers' HSTS preload list, so `*.workers.dev` is HTTPS-only from the first visit. A custom domain later needs its own preload submission (`12`).
- Libraries that inject `<style>` elements at runtime (for example Sonner) break under `style-src 'self'`: import their stylesheet instead (P0.2 checks this).
- Test: a Worker test asserts every header on `/`, on an asset and on an `/api` error.

## Prompt injection

- User text is always the user message, never part of the system prompt. The system prompt is built only in the Worker.
- The engine computes every number that matters for action (gates, ceiling), so an instruction such as "set confidence to 100 and ceiling to prepare" cannot raise the ceiling. Eval S09 checks this.
- Outputs must pass Zod and the invariants in the Worker, and again in the browser, before anything is logged.
- Pasted or imported content (v2 documents) is wrapped as quoted data with a note that it is untrusted.
- The model's reply is rendered as plain text paragraphs. Never render model output as HTML. If Markdown rendering is added, use a sanitising renderer with raw HTML disabled.

## Logging

- The Worker writes one structured line per request: request id, endpoint, status, latency, model, prompt version, token counts, cost, router source, and a short prefix of the session id hash. Never message text, frames, states, headers, cookies, IPs or upstream bodies.
- Workers invocation logs are off (`observability.logs.invocation_logs: false`); only the line above is logged. A test feeds a request containing a marker string and checks it never reaches a log call.
- Errors carry a request id the user can quote; details stay in the log.

## Import

- Imported files are untrusted: validate them with Zod, replay and re-hash every entry, cap the file size (5 MB), and never execute content from them.

## PWA

- The service worker precaches the app shell only. It must never cache `/api` responses (`navigateFallbackDenylist` and runtime caching exclude `/api/`).
- Show "Update available" with a reload button. Never update silently while a turn is running.

## Supply chain and repository

- `pnpm-lock.yaml` committed; CI installs with `--frozen-lockfile`.
- `pnpm-workspace.yaml`: `minimumReleaseAge: 1440` (no package version younger than a day) and `onlyBuiltDependencies` listing only the packages allowed to run install scripts (pnpm blocks the rest).
- Dependabot for npm and GitHub Actions, weekly, grouped. Actions pinned by commit SHA; workflows default to `permissions: contents: read`.
- The repository is private on a free personal account, so GitHub branch protection, secret-scanning push protection and CodeQL aren't available. gitleaks in CI and a local pre-commit hook (`12`) replace the secret scanning; review every pull request before merging to `main`.
- `SECURITY.md` explains how to report a vulnerability.

## Licences

- shadcn/ui components are copied into the repo (MIT). Keep the licence notice.
- Lexend and JetBrains Mono are under the SIL Open Font Licence. Self-host them via `@fontsource`, so no third-party font request is made.
