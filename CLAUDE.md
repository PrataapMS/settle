# Settle: instructions for the coding agent

You are implementing Settle, a local-first decision helper: a conversation on the left, a live decision panel on the right. The design is approved. Your job is to build it phase by phase from `plan/PLAN.md`.

## Read first, in this order

1. `README.md` and `docs/README.md`: what Settle is, and what is in each folder
2. `plan/PLAN.md`: phases and tasks; work on one task at a time, in order
3. `docs/02-architecture.md`: stack, module layout, the turn sequence
4. `docs/04-engine-rules.md`: the rules the engine must reproduce exactly
5. `docs/10-security-and-privacy.md`: the security controls every API change must keep
6. The doc for the task at hand (each task names its docs)

## Non-negotiable rules

1. **`src/core` is pure.** No React, no Dexie, no fetch, no `Date.now()`, no randomness. Times and ids come in as arguments. Enforce with an ESLint import restriction.
2. **The engine owns the numbers.** Totals, metrics, gate status, evidence strength, ceiling, bound status, system confidence, deltas, belief history, calibration and hashes are computed in `src/core`, never taken from model output.
3. **Golden fixtures are the spec.** `fixtures/*/expected/*.json` were produced by `tools/reference_engine.py`. Your engine must match them as canonical JSON. Never edit expected files by hand. If a rule must change, change the reference engine, regenerate, update `docs/04-engine-rules.md` and add an entry in `docs/11-decisions-log.md`, all in the same commit.
4. **Validate every model output** with Zod, then the invariants. One repair call at most. Nothing is written to the log unless it passes.
5. **The log is append-only.** State is derived by `replay(log)`. Never mutate past entries.
6. **Messages that don't move the decision never change state.** Only routes `new_decision`, `adds_evidence`, `changes_preference` and `challenges_analysis` can produce a decision turn; user overrides are logged with `source: "user"`. Free-form meta questions may call the model read-only (no schema, nothing written to state).
7. **Secrets stay in the Worker.** The browser never holds an API key and never calls OpenRouter, Jev or any third party (except the Turnstile widget); it calls same-origin `/api/*` only. Keys live in `.dev.vars` (gitignored) locally and in `wrangler secret` in deployed environments. Never in source, `wrangler.jsonc` `vars`, `VITE_*` variables, logs, error responses or exports. Never log message text.
8. **Render model text as text.** No `dangerouslySetInnerHTML` for model output.
9. **Schemas:** keep the Zod schemas and `/schemas/*.json` in parity (there is a test). The JSON files are what the model sees.
10. **Prompts** live in `/prompts` and are imported by the Worker with `?raw` (`worker/llm/prompts.ts`). Bump the version tag on every change.
11. **Every model-backed endpoint goes through `withGuards`** (origin check, size cap, session, rate limits, quota reserve and settle). The browser sends data, never prompts, schemas, model parameters or non-allowlisted model ids. Security controls in `docs/10` are not optional; changing one needs a decisions-log entry.

## Working style

- Before coding a task, restate its acceptance criteria and list the files you will touch.
- Write the tests first for anything in `src/core`.
- Keep commits small, one task per commit, message `P<phase>.<task>: <summary>`.
- Tick the task in `plan/PLAN.md` when its acceptance criteria pass, and note anything deferred under the task.
- Ask before adding a dependency that isn't listed in `plan/PREREQUISITES.md`.
- Ask before changing a public interface in `docs/02-architecture.md`, a schema or an engine rule.
- When a doc is ambiguous, prefer the reference engine, then the prototype, then ask.

## Commands (once the project exists)

| Command | Does |
|---|---|
| `pnpm dev` | Vite dev server with the Worker running in `workerd`, live models (needs `.dev.vars`) |
| `pnpm dev:mock` | Same, with the Worker in `LLM_MODE=mock` (no keys needed) |
| `pnpm test` | Vitest: unit, golden, schema parity, components |
| `pnpm test:e2e` | Playwright with the mock LLM, plus axe checks |
| `pnpm eval` | Router and scenario evals against live models (costs credits) |
| `pnpm lint` / `pnpm typecheck` | ESLint, `tsc -b` |
| `pnpm check:kit` | Reference-engine selftest, both fixture checks, hash vectors |
| `python3 tools/reference_engine.py --check <conv> <expected>` | Confirms expected fixtures are current |
| `python3 tools/build_schemas.py` | Regenerates `/schemas` from their definitions |

## Definition of done (every task)

- Acceptance criteria in `plan/PLAN.md` pass.
- `pnpm lint`, `pnpm typecheck` and `pnpm test` are green.
- New behaviour has tests; UI work is checked in all four themes at desktop width and at 390 px.
- No secrets, no `console.log` left in, no unused exports.
- Any new or changed `/api` behaviour has Worker tests for its security paths (`docs/09`, Worker and security).
