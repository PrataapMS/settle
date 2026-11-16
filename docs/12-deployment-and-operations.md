# 12 · Deployment and operations

Settle runs as one Cloudflare Worker with static assets on the free plan. This doc covers environments, configuration, secrets, CI/CD, the free-plan budget and what to do when something goes wrong. Security rules themselves are in `10-security-and-privacy.md`.

## Environments

| Environment | Worker | URL | Deployed | OpenRouter key | Budgets |
|---|---|---|---|---|---|
| Local, mock | (in Vite) | `localhost:5173` | `pnpm dev:mock` | none | n/a |
| Local, live | (in Vite) | `localhost:5173` | `pnpm dev` | development key, $5 limit | $1 a day |
| Staging | `settle-staging` | `settle-staging.<account>.workers.dev` | manually, by the maintainer (`pnpm wrangler deploy --env staging`) | development key | $1 a day, $5 a month |
| Production | `settle` | `settle.<account>.workers.dev` | major release tags `vX.0.0`, after approval | production key, monthly limit ≥ global monthly budget | $5 a day, $25 a month |

- Each environment has its own Turnstile widget (hostname bound) and its own secrets.
- `preview_urls: false` on both Workers: preview URLs would expose unreviewed code with real keys.
- The mock gateway refuses to start when `ENVIRONMENT` is `production` or `staging`.

## Configuration

`wrangler.jsonc` holds everything that is not secret. Bindings are not inherited by environments in Wrangler, so each environment repeats them. Sketch (P0.4 writes the real file):

```jsonc
{
  "name": "settle",
  "main": "worker/index.ts",
  "compatibility_date": "2026-10-30",
  "workers_dev": true,
  "preview_urls": false,
  "assets": { "directory": "./dist/client", "not_found_handling": "single-page-application", "run_worker_first": ["/api/*"] },
  "observability": { "enabled": true, "logs": { "invocation_logs": false } },
  "vars": {
    "ENVIRONMENT": "production",
    "TURNSTILE_SITE_KEY": "<public site key>",
    "MODEL_ALLOWLIST": "anthropic/claude-sonnet-5.5,anthropic/claude-haiku-5.5",
    "LIMITS": "{\"session_daily_usd\":0.75,\"ip_daily_usd\":2,\"global_daily_usd\":5,\"global_monthly_usd\":25}"
  },
  "durable_objects": { "bindings": [ { "name": "QUOTA", "class_name": "QuotaDO" }, { "name": "BUDGET", "class_name": "BudgetDO" } ] },
  "migrations": [ { "tag": "v1", "new_sqlite_classes": ["QuotaDO", "BudgetDO"] } ],
  "ratelimits": [
    { "name": "RL_SESSION_TURN", "namespace_id": "1001", "simple": { "limit": 6, "period": 60 } },
    { "name": "RL_SESSION_ROUTE", "namespace_id": "1002", "simple": { "limit": 20, "period": 60 } },
    { "name": "RL_IP_API", "namespace_id": "1003", "simple": { "limit": 60, "period": 60 } },
    { "name": "RL_IP_SESSION", "namespace_id": "1004", "simple": { "limit": 5, "period": 60 } }
  ],
  "env": { "staging": { "name": "settle-staging", "vars": { "ENVIRONMENT": "staging" } /* plus the same bindings */ } }
}
```

Check the exact keys against Cloudflare's current Wrangler docs in P0.4; the shape above is the intent.

## Secrets

Set once per environment, never echoed, never committed:

```sh
pnpm wrangler secret put OPENROUTER_API_KEY            # production
pnpm wrangler secret put OPENROUTER_API_KEY --env staging
# likewise: JEV_API_KEY, TURNSTILE_SECRET_KEY, SESSION_SECRET, IP_HASH_SECRET
openssl rand -base64 32                                # value for SESSION_SECRET and IP_HASH_SECRET
```

Locally, copy `.dev.vars.example` to `.dev.vars` and fill it in. `.dev.vars` is gitignored; `pnpm dev:mock` needs none of the values.

## CI/CD (GitHub Actions)

| Workflow | Trigger | Steps |
|---|---|---|
| `ci.yml` | push to `main`, pull request | install (`--frozen-lockfile`), `pnpm lint`, `pnpm typecheck`, `pnpm test`, `pnpm check:kit`, `pnpm build`, scan `dist/` for secrets, gitleaks, dependency review (pull requests); `pnpm test:e2e` from P3 |
| `codeql.yml` | push to `main`, pull request, weekly | CodeQL for TypeScript, Python and workflows |
| `pr-title.yml` | pull request | title matches `P<phase>.<task>: …` or a `Fix:`, `Docs:`, `Chore:`, `Deps:`, `Release:` prefix |
| `release.yml` | tag `vX.Y.Z` | tag must equal `package.json` version; `ci.yml` checks; GitHub Release with generated notes (`v0.*` marked pre-release); **deploy only for `vX.0.0` (X ≥ 1)**, after approval in the `production` environment, via `pnpm exec wrangler deploy` |
| Dependabot | weekly | npm and Actions updates, grouped |

### Releases and deploys

- Minor and patch releases (`v1.2.0`, `v1.2.3`) publish a GitHub Release only. Nothing is deployed.
- A major release deploys production: bump `package.json` to `X.0.0`, merge, tag `vX.0.0` on `main`, push the tag. The deploy job waits for the maintainer to approve it in the `production` environment.
- Staging deploys are manual, from a maintainer's machine, and never automatic.
- Settle deploys only to Cloudflare. No other host (Netlify, Vercel, …) is configured or used.

- Actions are pinned by commit SHA; workflows run with `permissions: contents: read` unless a job needs more.
- `CLOUDFLARE_API_TOKEN` (Workers Scripts: Edit, this account only) and `CLOUDFLARE_ACCOUNT_ID` are secrets of the `production` environment, so only the approved deploy job can read them.
- Public repositories get free Actions minutes; a CI run should still stay under 5 minutes.
- Local secret check: `brew install gitleaks`; the pre-commit hook in `.githooks/` runs it on staged changes (`pnpm install` sets `core.hooksPath`).

## Free-plan budget

| Resource | Free allowance | Settle's use |
|---|---|---|
| Static asset requests and bandwidth | Unlimited | The app shell |
| Worker requests | 100,000 a day, hard stop (no bill) | `/api` only; about 3 per decision turn |
| Worker CPU | 10 ms per request | Waiting on `fetch` doesn't count. Zod and invariants on a large output might; spike S2 measures it. If it's over, Workers Paid is $5 a month |
| Durable Objects (SQLite) | Included on the free plan, with daily limits | About 6 requests per model call |
| Rate Limiting bindings | Included | |
| Turnstile | Free | One challenge per session per day |

Model spend is the only real cost, and it is capped by the budgets above and the OpenRouter credit limit.

## Monitoring and alerts (v1)

- Workers Logs: the metadata line per request (`10`, Logging). Filter by `status`, `endpoint`, `cost`.
- The Worker logs `alert=budget_80`, `alert=budget_hit`, `alert=upstream_auth` (OpenRouter 401/402) and `alert=jev_down` once per period. Review them weekly, or add a push alert in P7.
- OpenRouter's dashboard shows spend per key; its credit limit stops spend even if everything else fails.

## Runbook

| Situation | Do this |
|---|---|
| A key may have leaked | Revoke it in OpenRouter (or TypeSafe), create a new one, `wrangler secret put` it, redeploy, check spend for the period |
| Budget hit early | Check logs for one IP hash or session prefix dominating; lower the per-IP or per-session limits in `vars`; deploy |
| Bot wave | Rotate `SESSION_SECRET` (and clear `SESSION_SECRET_PREVIOUS`) to end every session; raise the Turnstile widget to "managed" mode; lower limits |
| OpenRouter down | The app shows `upstream_unavailable`; nothing to do unless it lasts; reading and export still work |
| Bad deploy | `wrangler rollback` to the previous version, then fix forward |

## Custom domain (later)

Adding a domain to Cloudflare enables WAF rate-limiting rules at the edge (free plan: one rule), Bot Fight Mode, HSTS preload for the domain, and email alerts through Email Routing. Do it before any wider launch; the Worker code doesn't change.
