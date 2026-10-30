# 07 · LLM integration (OpenRouter and Jev)

## Roles

| Job | Who | Called when |
|---|---|---|
| Turn check | Jev; fallback: small model via OpenRouter; `/commands` by rule | Every message |
| Frame and decision turns | Reasoning model via OpenRouter | Applied routes only |
| Meta answers | Templates; reasoning model only for free-form meta questions | Meta route |
| Record guard (optional) | Jev | After each validated decision turn |
| Intuition check (optional) | Jev | After each decision turn, if enabled |

## OpenRouter

### Request

```http
POST https://openrouter.ai/api/v1/chat/completions
Authorization: Bearer <key>
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
  "provider": {"require_parameters": true},
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
| No response after 45 s | Abort with `AbortController`, then offer Retry |
| 401 (bad key) or 402 (out of credits) | No retry; open key settings with the message |
| Invalid JSON, Zod failure or invariant failure | One repair call (`prompts/repair.md`), then give up as `failed` |

Confirm the exact meaning of each error code against OpenRouter's error-handling docs during spike S1, and map them in `llm/openrouter.ts`.

### Keys: local development

Never put a key in client code or in `VITE_*` variables (Vite inlines those into the bundle). Use the dev server as a proxy:

```ts
// vite.config.ts
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
  // Vite does not put .env.local into process.env while loading the config: load it explicitly.
  // The empty prefix loads all variables, but only into this Node process, never into the client bundle.
  const env = loadEnv(mode, process.cwd(), '');
  return {
    server: {
      proxy: {
        '/or': {
          target: 'https://openrouter.ai/api/v1',
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/or/, ''),
          configure: (proxy) => {
            proxy.on('proxyReq', (req) => req.setHeader('Authorization', `Bearer ${env.OPENROUTER_API_KEY}`));
          },
        },
      },
    },
    // ...plugins
  };
});
```

`.env.local` (gitignored): `OPENROUTER_API_KEY=sk-or-…`. In development, the client calls `/or/chat/completions`. Check the proxy with an authenticated call, such as a 1-token chat completion: `/models` works without a key, so it proves nothing.

### Keys: users in production (no Settle account)

OpenRouter OAuth PKCE gives each user their own key, billed to their own OpenRouter credits:

1. Generate `code_verifier` (random, 43 to 128 characters) and `code_challenge = base64url(sha256(verifier))`. Store the verifier in `sessionStorage`.
2. Redirect to `https://openrouter.ai/auth?callback_url=<origin>/oauth/callback&code_challenge=<challenge>&code_challenge_method=S256&state=<random>`.
3. On `/oauth/callback?code=…&state=…`, check `state`, then `POST https://openrouter.ai/api/v1/auth/keys` with `{code, code_verifier, code_challenge_method: "S256"}`.
4. Store the returned `key` in the `ui` store. Codes are single-use and expire after 10 minutes.
5. Localhost callbacks work on any port, so this can be tested locally.

Settings also offers "Paste a key" for people who already have one, and "Disconnect", which deletes the stored key.

Spike S2 confirms that browser requests to `openrouter.ai/api/v1/chat/completions` pass CORS from your origin. If they don't, add a minimal Netlify Function that forwards the user's key without storing it.

### Models (settings, with defaults)

| Setting | Default | Notes |
|---|---|---|
| Reasoning model | `anthropic/claude-sonnet-5.5` | Must list `response_format` / structured outputs on its OpenRouter page |
| Router fallback model | a small, fast model, e.g. `anthropic/claude-haiku-5.5` | Check exact ids on openrouter.ai/models |
| Temperature | 0.3 (reasoning), 0 (router) | |

Model and prompt versions are written into every log entry, so evals can compare them.

## Jev (TypeSafe)

Jev returns typed choices with calibrated probabilities instead of text, which fits the turn check, the record guard and the intuition check (`prompts/jev-questions.md`). It is in early access: the published latency was measured from the US West Coast, and pricing may be subsidised.

- Put it behind the `Router` interface (`llm/router/jev.ts`). Its config: endpoint, key, timeout 1.5 s.
- If it is disabled, times out or errors, call `ModelRouter` (OpenRouter with `prompts/router.md` and `schemas/route.schema.json`). The user never sees the difference, but `route.source` records it.
- Keep the Jev key out of the client bundle, the same way as the OpenRouter key: dev proxy locally, and a small function in production unless TypeSafe offers a user-auth flow.
- Spike S3 confirms the request and response shape against TypeSafe's docs before any code depends on it.

## Context sent per turn

- Frame JSON plus state JSON (about 2 to 4 KB) plus the last 2 decision turns' prose. Never the whole thread: cost per turn stays flat as the thread grows.
- The user's message as the user turn, unchanged.
- Never include: keys, other decisions, telemetry, or the full record history.
