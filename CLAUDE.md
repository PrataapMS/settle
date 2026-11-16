# Settle: instructions for the coding agent

## Project Overview

- Purpose: Settle, a local-first decision helper: a conversation on the left, a live decision panel on the right, with a pure engine that owns every number.
- Stack: TypeScript, React 19 + Vite, shadcn/ui on Tailwind, Zustand, Dexie (IndexedDB), Zod; one Cloudflare Worker serving the app and `/api/*` (model calls via OpenRouter / Jev); Vitest, Playwright; Python 3 reference engine in `tools/`. Package manager: pnpm, Node >= 24.
- Key directories: `src/` browser app (`src/core` is the pure engine), `worker/` Cloudflare Worker, `prompts/` and `schemas/` what the model sees, `fixtures/` golden fixtures, `tools/` reference engine and checks, `docs/` specs, `plan/` phases and tasks (local only), `evals/` router and scenario evals, `design/` approved design.

You are implementing it phase by phase from `plan/PLAN.md`. The design is approved. The repository is **public**; `plan/` and `docs/11-decisions-log.md` are local only (see Public and local).

## Commands

- Install: `pnpm install`
- Test: `pnpm test` (plus `pnpm test:e2e`, `pnpm check:kit`)
- Lint/format: `pnpm lint`, `pnpm typecheck`
- Build: `pnpm build`
- After making code changes, run the test and lint commands before reporting the task as done.

Full list (some scripts land in later phases; check `package.json`):

| Command | Does |
|---|---|
| `pnpm dev` | Vite dev server with the Worker running in `workerd`, live models (needs `.dev.vars`) |
| `pnpm dev:mock` | Same, with the Worker in `LLM_MODE=mock` (no keys needed) |
| `pnpm test` | Vitest: unit, golden, schema parity, components |
| `pnpm test:e2e` | Playwright with the mock LLM, plus axe checks |
| `pnpm eval` | Router and scenario evals against live models (costs credits) |
| `pnpm lint` / `pnpm typecheck` | ESLint, `tsc -b` |
| `pnpm build` | `tsc -b` and `vite build` |
| `pnpm check:kit` | Reference-engine selftest, both fixture checks, hash vectors |
| `python3 tools/reference_engine.py --check <conv> <expected>` | Confirms expected fixtures are current |
| `python3 tools/build_schemas.py` | Regenerates `/schemas` from their definitions |

## Starting a session

Pick up where the last session stopped, without being asked:

1. `git fetch --prune`, `git status`. If a task branch has uncommitted or unpushed work, finish that task first.
2. `gh pr list --author @me --state open`: if a task PR is open, get its CI green, merge it (squash) and finish its bookkeeping.
3. `gh project item-list 2 --owner PrataapMS --format json`: resume any item **In Progress**.
4. Otherwise take the first unticked task in `plan/PLAN.md` (spikes S1 to S3 may run alongside P1) whose issue is not blocked by an open prereq. Find it with `gh issue list --search "<id> in:title"`.
5. Tell the user in one line which task you are starting, then follow `plan/WORKFLOW.md`.

Stop and ask when a task needs access you don't have (keys, accounts, `needs-access`), a new dependency, or a public interface, schema or engine-rule change.

## Read first, in this order

1. `README.md` and `docs/README.md`: what Settle is, and what is in each folder
2. `plan/PLAN.md` and `plan/WORKFLOW.md` (local): phases, tasks and how work moves to `main`; one task at a time, in order. If `plan/` is missing (fresh clone), ask the user for it
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

## Commits and pull requests

- Commits carry the user's name only. **Never add `Co-Authored-By` or any AI attribution** to commits, and no "Generated with" line in PR bodies (`.githooks/commit-msg` strips them; `.claude/settings.json` turns attribution off).
- Keep commits clean and short: subject `P<phase>.<task>: <summary>` (≤ 60 characters, imperative), then at most 2 to 3 lines saying what changed and why. No step-by-step narration.
- PR bodies: `Closes #<n>`, a short "What changed" list and the ticked acceptance criteria.

## Public and local

- **Local only (gitignored), never commit or push:** `plan/` (PLAN, WORKFLOW, PREREQUISITES, DISTRIBUTION) and `docs/11-decisions-log.md`.
- Public files, commits, issues and PRs never link to local files and never quote decision or open-item ids (D1, O2, …) or decision rationale. Describe the change, not the decision history.
- Issues are public: a one-line user-facing goal plus acceptance criteria. Task detail stays in `plan/PLAN.md`.
- `ROADMAP.md` is the public plan: features per phase with status. Update it (and the README roadmap table) when a phase starts or finishes or its features change.
- Keep `README.md` in line with `plan/DISTRIBUTION.md` (badges, previews, topics, release notes).

## Releases and deploys

- Production deploys only through `release.yml` on a major tag `vX.0.0`, after approval in the `production` environment. Minor and patch tags publish a GitHub Release only.
- Never create a release tag, approve a deployment or run `wrangler deploy` (staging included) without the user's explicit confirmation in the current session.
- **Never deploy anything to Netlify** (or any other host) unless the user confirms in the current session.
- Never push to `main` directly, even though the owner can bypass the ruleset. Every change goes through a PR.

## Definition of done (every task)

- Acceptance criteria in `plan/PLAN.md` pass.
- `pnpm lint`, `pnpm typecheck` and `pnpm test` are green.
- New behaviour has tests; UI work is checked in all four themes at desktop width and at 390 px.
- No secrets, no `console.log` left in, no unused exports.
- Any new or changed `/api` behaviour has Worker tests for its security paths (`docs/09`, Worker and security).

## Conventions

- Before coding a task, restate its acceptance criteria and list the files you will touch.
- Write the tests first for anything in `src/core`.
- Follow `plan/WORKFLOW.md`: one branch and one PR per task (`p<phase>.<task>-<slug>`), never commit to `main`; commits and PR title `P<phase>.<task>: <summary>`; PR body has `Closes #<issue>`; squash-merge only when CI is green.
- Each task has a GitHub issue (sub-issue of its phase epic) on the **Settle** project (`gh project view 2 --owner PrataapMS`). Move its Status to In Progress when you start, In Review when the PR opens; tick its AC checkboxes as they pass.
- Tick the task in `plan/PLAN.md` when its acceptance criteria pass, and note anything deferred under the task with a new follow-up issue.
- Ask before adding new dependencies (anything not listed in `plan/PREREQUISITES.md`).
- Ask before changing a public interface in `docs/02-architecture.md`, a schema or an engine rule.
- When a doc is ambiguous, prefer the reference engine, then the prototype, then ask.
