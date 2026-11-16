# 07 · LLM integration (OpenRouter and Jev)

## Roles

| Job | Who | Called when |
|---|---|---|
| Turn check | Jev; fallback: small model via OpenRouter; `/commands` by rule | Every message |
| Frame and decision turns | Reasoning model via OpenRouter | Applied routes only |
| Meta answers | Templates; reasoning model only for free-form meta questions | Meta route |
| Record guard (optional) | Jev | After each validated decision turn |
| Intuition check (optional) | Jev | After each decision turn, if enabled |

All of these calls are made by the Worker behind `/api` (`02-architecture.md`, API); `/commands` are handled in the browser with no network call.

## OpenRouter

### Request (sent by the Worker)

```http
POST https://openrouter.ai/api/v1/chat/completions
Authorization: Bearer <OPENROUTER_API_KEY>
Content-Type: application/json
HTTP-Referer: https://<your-app-host>        (optional, app attribution)
X-OpenRouter-Title: Settle                   (optional; X-Title also accepted)
```

```json
{
  "model": "anthropic/claude-sonnet-5.5",
  "messages": [
    {"role": "system", "content": "<shared-rules + turn prompt, placeholders filled>"},
    {"role": "user", "content": "<user's message, unchanged>"}
  ],
  "response_format": {
    "type": "json_schema",
    "json_schema": {"name": "settle_decision_turn", "strict": true, "schema": { "...": "schemas/decision-turn-output.schema.json without $schema/title" }}
  },
  "provider": {"require_parameters": true, "data_collection": "deny"},
  "max_tokens": 6000,
  "temperature": 0.3
}
```

- `provider.require_parameters: true` sends the request only to providers that support every parameter you sent, including `response_format`. Without it, a provider that ignores the schema can be chosen silently.
- Strict schema enforcement is native only on some providers; others treat the schema as a strong hint. Always validate with Zod.
- Consider the `response-healing` plugin for non-streaming JSON (check the plugin syntax in OpenRouter's docs during spike S1).
- Read `choices[0].message.content`, then `JSON.parse`, then Zod. Treat `finish_reason` `length` as a failure to retry with a higher `max_tokens`, and `content_filter` as a failure with no retry.
- Record `usage.prompt_tokens`, `usage.completion_tokens` and `usage.cost` in telemetry.
- Parameters a model doesn't support are ignored, not rejected. That's another reason to keep `require_parameters` on.

### Streaming (later)

v1 is non-streaming: one call returns the whole record, and the UI shows a progress state ("Checking… Reasoning… Validating…"). Streaming the reply prose as it is generated needs either partial-JSON parsing or a two-call design (prose stream, then a record call). Add it only if p95 latency is a problem.

### Retries and timeouts

| Condition | Action |
|---|---|
| Network error, 429, 5xx | Retry up to 2 times (1 s, then 3 s, with jitter). OpenRouter already falls back across providers on 5xx and rate limits. |
| No response after 45 s | The Worker aborts with `AbortController` and answers 504; the browser offers Retry |
| 401 (bad key) or 402 (out of credits) | No retry; answer 503 `service_unavailable` and log `alert=upstream_auth`. The browser never sees the upstream message |
| Invalid JSON, Zod failure or invariant failure | One repair call (`prompts/repair.md`), then give up as `failed` |

Confirm the exact meaning of each error code against OpenRouter's error-handling docs during spike S1, and map them in `worker/llm/openrouter.ts`. Retries run in the Worker; each attempt is metered.

### Where calls run and where keys live

Every OpenRouter and Jev call is made by the Cloudflare Worker (`worker/llm/`). The browser calls same-origin `/api/*` endpoints (`02-architecture.md`, API) and never sees a key, a system prompt or an upstream response body. There is no OAuth, no pasted key and no key in IndexedDB.

| Secret | Where it lives | Who reads it |
|---|---|---|
| `OPENROUTER_API_KEY` | `wrangler secret put` per environment; `.dev.vars` locally | `worker/llm/openrouter.ts` only |
| `JEV_API_KEY` | same | `worker/llm/router/jev.ts`, `guard.ts` |
| `TURNSTILE_SECRET_KEY` | same | `worker/security/turnstile.ts` |
| `SESSION_SECRET`, `SESSION_SECRET_PREVIOUS` | same (32 random bytes, base64) | `worker/security/session.ts` |
| `IP_HASH_SECRET` | same | `worker/security/limits.ts`, `quota.ts` |

- `.dev.vars` is gitignored; `.dev.vars.example` lists the names with empty values. `wrangler.jsonc` `vars` hold only non-secret settings (limits, model allowlist, Turnstile site key).
- Use separate OpenRouter keys for development, staging and production, each with its own credit limit set in the OpenRouter dashboard. The production key's monthly limit is the last line of defence on spend (`10-security-and-privacy.md`, Spend).
- In development, `pnpm dev` runs the Worker inside Vite (`@cloudflare/vite-plugin`), reading `.dev.vars`. Check the wiring with an authenticated call (a 1-token frame turn); `/models` works without a key, so it proves nothing.
- The Worker reads `usage.cost` from each response and commits it to the quota meters before answering.

### Provider preferences

The Worker adds to every request:

```json
"provider": {"require_parameters": true, "data_collection": "deny"}
```

`data_collection: "deny"` restricts routing to providers that don't store or train on prompts. Spike S1 checks that the chosen models still have a provider under this rule, and whether `zdr: true` (zero data retention) is available for them; if it is, turn it on.

### Models (server-side allowlist)

The Worker holds the allowlist in `wrangler.jsonc` `vars` (`MODEL_ALLOWLIST`). Settings shows its labels; the browser sends only an allowlisted id, and anything else is rejected with 400.

| Setting | Default | Notes |
|---|---|---|
| Reasoning model | `anthropic/claude-sonnet-5.5` | Must list `response_format` / structured outputs on its OpenRouter page |
| Router fallback model | a small, fast model, e.g. `anthropic/claude-haiku-5.5` | Check exact ids on openrouter.ai/models |
| Temperature | 0.3 (reasoning), 0 (router) | Fixed in the Worker |
| `max_tokens` | 6000 (frame and decision turns), 300 (router), 600 (meta) | Fixed in the Worker; also bounds cost per call |

Model and prompt versions are written into every log entry, so evals can compare them.

## Jev (TypeSafe)

Jev returns typed choices with calibrated probabilities instead of text, which fits the turn check, the record guard and the intuition check (`prompts/jev-questions.md`). It is in early access: the published latency was measured from the US West Coast, and pricing may be subsidised.

- Put it behind the `Router` interface (`worker/llm/router/jev.ts`). Its config: endpoint (a var), key (a secret), timeout 1.5 s.
- If it is disabled, times out or errors, call `ModelRouter` (OpenRouter with `prompts/router.md` and `schemas/route.schema.json`). The user never sees the difference, but `route.source` records it.
- The Jev key is a Worker secret, like the OpenRouter key. Jev calls are metered and rate limited like model calls.
- Spike S3 confirms the request and response shape against TypeSafe's docs before any code depends on it, and decides whether Jev ships in v1. Jev becomes the default turn check only if, measured from the Worker: accuracy on `fixtures/router-cases.json` is at least 90%, p95 latency is at most 600 ms, cost per check is below the fallback model's, and TypeSafe's terms allow server-side use for anonymous public users. Otherwise `ModelRouter` stays the default and Jev stays behind a flag.

## Context sent per turn

- Frame JSON plus state JSON (about 2 to 4 KB) plus the last 2 decision turns' prose. Never the whole thread: cost per turn stays flat as the thread grows.
- The user's message as the user turn, unchanged.
- Never include: keys, other decisions, telemetry, or the full record history.
- The Worker caps what it accepts (`10-security-and-privacy.md`, Input limits) and rebuilds the context from the validated request, so the browser cannot add extra messages.
