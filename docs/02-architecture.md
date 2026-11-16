# 02 · Architecture

## Shape

Settle is a single-page app served by one Cloudflare Worker. The browser holds all decision data (IndexedDB) and runs the engine. The Worker serves the static files and a small same-origin API, `/api/*`, that is the only place model and Jev calls are made. No API key ever reaches the browser, and the browser never talks to a third party except Turnstile's challenge.

```
Browser (React SPA, engine, IndexedDB)
   │  same origin only: GET /assets/*, POST /api/*   (CSP connect-src 'self')
   ▼
Cloudflare Worker  "settle"
   ├─ static assets (free, unlimited)          ← _headers: CSP, HSTS, etc.
   └─ /api gateway
        security: origin check → body cap → session (Turnstile) → rate limits → quota reserve
        jobs:     route · frame-turn · decision-turn · meta · intuition
        llm:      server-side prompts + schemas → OpenRouter / Jev → Zod + invariants → one repair
        meter:    commit actual usage.cost to QuotaDO (session, IP) and BudgetDO (global)
   │  secrets: OPENROUTER_API_KEY, JEV_API_KEY, TURNSTILE_SECRET_KEY, SESSION_SECRET, IP_HASH_SECRET
   ▼
OpenRouter · TypeSafe Jev · Turnstile siteverify
```

## Stack

| Concern | Choice | Notes |
|---|---|---|
| App | React + TypeScript (strict) on Vite, as a PWA | Base: create-vite `react-ts` |
| UI | shadcn/ui on Tailwind CSS, lucide-react icons | Components copied into `src/components/ui` by the shadcn CLI |
| Client state | Zustand for UI state; Dexie live queries for data | No global data cache beyond Dexie |
| Storage | IndexedDB via Dexie | Stores: `decisions`, `log`, `ui`, `checks`, `telemetry` (`06-state-and-storage.md`) |
| Validation | Zod | One source for types; JSON Schemas in `/schemas` mirror it for the model; the API request and response shapes live in `src/core/schema/api.ts` and are checked on both sides |
| Hosting and API | Cloudflare Workers with static assets, on `*.workers.dev` | One Worker serves the app and `/api`; free plan (`12-deployment-and-operations.md`) |
| Dev server | Vite with `@cloudflare/vite-plugin` | Runs the Worker in `workerd` inside `pnpm dev`, so dev and production run the same code |
| Abuse control | Turnstile, Workers Rate Limiting bindings, Durable Objects (`QuotaDO`, `BudgetDO`) | Public, anonymous v1; details in `10-security-and-privacy.md` |
| Reasoning model | OpenRouter chat completions with `response_format: json_schema`, called by the Worker | Model chosen from a server-side allowlist; default `anthropic/claude-sonnet-5.5` |
| Turn check | Jev (TypeSafe), fallback: small model via OpenRouter, both called by the Worker | Behind one `Router` interface; Jev only if spike S3 meets its bar |
| Hashing | Web Crypto SHA-256 over canonical JSON (RFC 8785 style) | See `04-engine-rules.md` |
| Tests | Vitest (unit, golden), Testing Library (components), `@cloudflare/vitest-pool-workers` (Worker, in `workerd`), Playwright (end to end) | |
| PWA | vite-plugin-pwa | Precache app shell only, never `/api` |

## Module layout

```
src/                    the browser app
  core/                 pure TypeScript, no React, no I/O, no Date.now(); imported by the Worker too
    schema/             Zod schemas: frame, record, route, state, log entry, decision file, api (requests and responses)
    expr/               tokenizer + parser + evaluator for metric expressions
    engine/             computeState(), gates, totals, evidence, ceiling, deltas, invariants
    frame/              validateFrame(), checkSyntax(), splitProposal(), applyProposal(), applyFrameEdit()
    log/                reducer: replay(log) -> states; canonical JSON; hashEntry()
    format/             toMarkdown(), toHtml(), toContractJson() for copy and export
  api/
    client.ts           typed fetch to /api/*: session bootstrap, error mapping, AbortController
    turnstile.ts        loads the Turnstile widget, gets a token for POST /api/session
    rule-router.ts      /commands, no network
    mock.ts             Gateway implementation from fixtures, for unit and component tests
  store/
    db.ts               Dexie schema and migrations
    repo.ts             appendEntry(), loadDecision(), listDecisions(), exportFile(), importFile()
    settings.ts         theme, density, model choice, panel sections (no keys: there are none in the browser)
  app/
    turn.ts             orchestrates one user message end to end (see sequence below)
  features/
    conversation/       message list, turn cards, clarify card, meta card, composer
    panel/              header, version stepper, tiles, sections, export
    decisions/          sidebar list, new decision, frame review dialog
    settings/           model, Jev toggle, privacy, usage left today, data
  components/ui/        shadcn components (generated)
  theme/                tokens.css (from design/tokens.css), ThemeProvider
worker/                 the Cloudflare Worker
  index.ts              fetch handler: /api/* dispatch, everything else to static assets
  http.ts               JSON responses, error envelope, security headers for /api
  security/
    origin.ts           Origin, Sec-Fetch-Site and content-type checks (CSRF)
    session.ts          HMAC-signed session cookie: mint, verify, rotate
    turnstile.ts        siteverify (hostname, action, single use)
    limits.ts           Rate Limiting bindings per session, per IP hash and per job
    quota.ts            QuotaDO (session and IP daily meters) and BudgetDO (global daily and monthly)
  llm/
    openrouter.ts       fetch wrapper: auth, provider preferences, retries, timeouts, error mapping
    reasoner.ts         buildMessages(), frameTurn(), decisionTurn(), Zod + invariants, one repair
    router/             Router interface, JevRouter, ModelRouter (fallback)
    guard.ts            record guard (Jev), optional
    meta.ts             free-form meta answer: plain text, small max_tokens
    prompts.ts          imports /prompts/*.md with ?raw and fills placeholders
    mock.ts             fixture-backed gateway for `pnpm dev:mock` and e2e; refuses to run when ENVIRONMENT=production
  env.ts                typed bindings and vars (generated by `wrangler types`)
public/_headers         security headers for static assets
wrangler.jsonc          Worker config: assets, bindings, vars (never secrets), environments
tests/
  golden/               replays the fixtures and compares with expected/
  router/               runs fixtures/router-cases.json against a router
  worker/               API, security and quota tests in workerd
evals/                  scenario harness (node script) and reports
```

Dependency rules, enforced with ESLint `no-restricted-imports`:
- `src/core` imports nothing outside itself except `zod`.
- `src/features` → `src/app` → `src/api`, `src/store`, `src/core`.
- `worker/` may import `src/core` and `/prompts`, nothing else from `src/`. `src/` never imports `worker/`.

## API

All endpoints are `POST` with `Content-Type: application/json` unless noted, same origin only, and need a valid session cookie except `GET /api/config` and `POST /api/session`. Request and response bodies are Zod schemas in `src/core/schema/api.ts`. Every model-backed response carries `meta: {model, prompt_version, router_source?, usage: {prompt_tokens, completion_tokens, cost}}` for the log entry and telemetry.

| Endpoint | Body | Returns | Calls |
|---|---|---|---|
| `GET /api/config` | | Turnstile site key, model allowlist (ids and labels), `jev_available`, limits summary | none |
| `POST /api/session` | `{turnstile_token}` | `Set-Cookie: __Host-settle_sid`; `{expires_at, usage}` | Turnstile siteverify |
| `GET /api/usage` | | Turns and budget left today for this session | QuotaDO |
| `POST /api/route` | `{text, ctx}` | `RouteResult` | Jev, else model router |
| `POST /api/frame-turn` | `{text, model?}` | `FrameTurnOutput` (validated) or `failed` with prose | OpenRouter |
| `POST /api/decision-turn` | `{text, frame, state, recent, route, model?}` | `DecisionTurnOutput` (validated), `guard_findings?`, or `failed` with prose | OpenRouter, Jev guard |
| `POST /api/meta` | `{question, state}` | `{answer}` plain text | OpenRouter |
| `POST /api/intuition` | `{frame, state}` | Jev choice and probabilities | Jev |

The gateway is not a model proxy. The browser cannot send a system prompt, a schema, a model id outside the allowlist, `max_tokens` or `temperature`; the Worker owns all of them. That keeps the endpoint from being useful as a free general-purpose model relay.

## One user message, end to end

Every user message ends in exactly one log entry (or none, before a decision exists). Nothing is written until the outcome is known, so a failed call never leaves half a turn. Model calls are steps that go through `/api`; the engine steps run in the browser.

```
composer.send(text)
  └─ app/turn.ts
       0. ensure session: if no valid cookie, Turnstile token → POST /api/session (once per 24 h)
       A. No current decision (new thread):
            route = api.route(text, {noDecision: true})                // new_decision | too_vague
            too_vague  → UI-only reply: "Tell me what you're deciding between…"; nothing logged; done
            new_decision → api.frameTurn(text)                         // Worker: prompt, OpenRouter, Zod, invariants, one repair
                           failed → UI-only error card with Retry; no decision row, nothing logged; done
                           → client re-validates with Zod (defence in depth)
                           → show the frame review dialog
                           → on confirm: create the decision row; append {kind:"decision", …} (+ {kind:"frame_edit"} if edited); done
                           → on cancel: nothing logged
       B. Existing decision:
         1. if text starts with "/" → ruleRouter(text) (browser, no network):
              /rewind vN → confirm dialog → append {kind:"rewind", to_v:N}; done
              other /commands → templated meta answer → append {kind:"meta", route:{route:"meta", source:"rule"}}; done
            else route = api.route(text, context)                     // Worker: Jev, else fallback model
         2. route = meta            → template, or api.meta(question, state) (read-only) → append {kind:"meta"}; done
            route = too_vague | off_topic → append {kind:"clarify"}; render the clarify card; done
            route applied, confidence < 0.7 → render "Should this update the decision?":
                 "Yes, apply it" → continue at 3 with route.source = "user"
                 "No, just a comment" → append {kind:"clarify", route, user_choice:"comment"}; done
         3. result = api.decisionTurn(text, frame, state, recentTurns, route)
              Worker: buildMessages → OpenRouter (structured output) → Zod → invariants(frameAfterAutoPart, record, heldPart)
                      → on failure one repair call → guard (optional, Jev) → meter usage
         4. result failed → append {kind:"failed", user_text, route, reason}; show the prose muted; done
         5. client re-runs Zod and invariants on the output; on failure append {kind:"failed"} as in 4
         6. append {kind:"decision", user_text, route, model, prompt_version, output, guard_findings?, override_of?}
         7. state = replay(log) (incrementally: apply the new entry to the cached state); cache on decisions.state
         8. UI re-renders from the Dexie live query; the panel shows v+1 with deltas; focus moves to the new turn card

  Override from a clarify card ("It is relevant: apply it anyway"):
       run B3–B8 with route = {route: "adds_evidence", confidence: 1, source: "user"} and override_of = <seq of the clarify entry>
```

Logged routes are `{route, confidence, source}`. The router's `reason` is shown in the UI tooltip but dropped before logging, so it never affects hashes.

## Key interfaces (TypeScript)

```ts
// browser: src/api; implemented by client.ts (HTTP) and mock.ts (fixtures)
interface Gateway {
  route(text: string, ctx: RouteContext, signal?: AbortSignal): Promise<RouteResult>;
  frameTurn(text: string, opts: CallOpts): Promise<TurnResult<FrameTurnOutput>>;
  decisionTurn(text: string, frame: Frame, state: State, recent: TurnPair[], route: Route, opts: CallOpts): Promise<TurnResult<DecisionTurnOutput>>;
  meta(question: string, state: State, opts: CallOpts): Promise<{ answer: string; meta: CallMeta }>;
}
type TurnResult<T> = { ok: true; output: T; meta: CallMeta; guard_findings?: GuardFinding[] }
                   | { ok: false; reason: string; prose: string | null; meta: CallMeta };

// worker: worker/llm
interface Router { classify(text: string, ctx: RouteContext, signal?: AbortSignal): Promise<RouteResult>; }
type RouteResult = { route: Route; confidence: number; reason: string; source: 'jev' | 'model' | 'rule' };

// core (pure); mirrors tools/reference_engine.py
function computeState(input: {
  frame: Frame; inputs: InputsState; record: DecisionRecord; prev: State | null;
  v: number; at: string; predictions: Prediction[]; newGateIds: Set<string>;
  cause?: 'decision' | 'frame_accept' | 'frame_edit'; baseV?: number | null;
}): State;   // belief is derived from prev; decision_id, title, frame, pending_frame_proposal, invariants and log_head are added by replay
function replay(log: LogEntry[]): { states: State[]; current: State | null };
function appendEntry(log: LogEntry[], partial: NewEntry): Promise<LogEntry>;   // assigns seq, prev_hash, hash
function verifyChain(log: LogEntry[]): Promise<{ ok: true } | { ok: false; seq: number }>;
```

## Error handling

The Worker answers every error with `{error: {code, message, retry_after_s?}}` and never forwards upstream bodies, stack traces or headers.

| Failure | HTTP | Behaviour in the browser |
|---|---|---|
| Missing or expired session | 401 `session_required` | Re-run Turnstile silently, mint a session, retry once |
| Turnstile failed | 403 `challenge_failed` | Show the visible Turnstile widget |
| Cross-origin or wrong content type | 403 / 415 | Not expected from the app; nothing logged |
| Request too large | 413 `too_large` | "That message is too long" with the limit |
| Rate limited | 429 `rate_limited` + `Retry-After` | Pending turn shows a countdown, then Retry |
| Daily allowance used (session or IP) | 429 `quota_exhausted` | "You've used today's turns; resets at 00:00 UTC". Reading and export still work |
| Global budget reached | 503 `budget_exhausted` | Banner: "Settle is resting until tomorrow". Composer disabled |
| Upstream 429 / 5xx after Worker retries | 502 `upstream_unavailable` | Retry button on the pending turn |
| Upstream timeout (45 s) | 504 `upstream_timeout` | Retry button |
| Schema or invariant failure after repair | 200 with `ok: false` | Reply prose in a muted card marked "Not applied: the analysis did not pass checks", with Retry; log `{kind:"failed", reason}` |
| OpenRouter 401/402 (Settle's key) | 503 `service_unavailable` | Generic banner; the Worker logs an `alert=upstream_auth` line (`12-deployment-and-operations.md`) |
| Jev unavailable | none | The Worker falls back to the model router silently; `source: "model"` |
| Import hash mismatch | none | Refuse the import; name the first bad sequence number |
