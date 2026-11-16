# 09 · Testing and evals

## Test layers

| Layer | Tool | What | Gate |
|---|---|---|---|
| Unit | Vitest | `core/expr`, gates, totals, evidence, ceiling, rounding, canonical JSON | Every PR |
| Golden | Vitest | Replay `fixtures/*/conversation.json`; compare every produced file with `fixtures/*/expected/*.json` as canonical JSON | Every PR; failures block merge |
| Schema parity | Vitest | Zod schemas → JSON Schema, compared structurally with `/schemas/*.json` | Every PR |
| Component | Vitest + Testing Library | Turn cards, clarify card, panel sections render from a fixture state; accordion state; copy buttons call the clipboard | Every PR |
| Worker and security | Vitest with `@cloudflare/vitest-pool-workers` (runs in `workerd` with real Durable Object and rate-limit bindings) | Every `/api` endpoint: Zod rejection, size caps, origin and content-type checks, session mint and verify (Turnstile test keys), 401/403/413/415/429/503 paths, quota reserve and settle, global budget cut-off, concurrency, security headers on assets and API, no secret or message text in responses or log calls, mock refuses to run in production | Every PR |
| End to end | Playwright | Full flows with a mock reasoner and router (fixture-driven): golden path, clarify, meta, rewind, export and import, themes; axe accessibility checks in all four themes | Every PR (mock), nightly (live, optional) |
| Router eval | Node script | `fixtures/router-cases.json` through the full routing path (`ruleRouter` for "/" messages first, then Jev or the fallback model) | Before changing router prompt or model |
| Scenario evals | Node script | `evals/scenarios.md` against the live stack | Before release; after any prompt or model change |

## Golden tests: how

```ts
// tests/golden/replay.test.ts
for (const dir of ['rent-or-buy', 'rent-or-buy-edits']) {
  const conv = load(`fixtures/${dir}/conversation.json`);
  const { log, states, final } = await replayFromEvents(conv);   // same as the reference engine's run()
  expect(canonical(log)).toBe(canonical(load(`fixtures/${dir}/expected/log.json`)));
  for (const s of states) expect(canonical(s)).toBe(canonical(load(`fixtures/${dir}/expected/state-v${s.v}.json`)));
  expect(canonical(final)).toBe(canonical(load(`fixtures/${dir}/expected/final-state.json`)));
}
```

When a golden test fails, diff field by field and fix the TypeScript engine. Change the reference engine only if the rule itself is meant to change, and then regenerate the fixtures (`python3 tools/reference_engine.py <conv> <expected>`), update `docs/04-engine-rules.md` and explain the rule change in the pull request, all in the same commit.

Add new golden fixtures for every engine bug found later: reproduce the bug as a conversation, generate expected files with the reference engine, then fix the TS engine.

## Mock reasoner and router

Two mocks share one fixture-backed core: `src/api/mock.ts` implements the browser `Gateway` for unit and component tests, and `worker/llm/mock.ts` answers the real `/api` endpoints when the Worker runs with `LLM_MODE=mock` (`pnpm dev:mock`, Playwright). End-to-end tests therefore exercise the real security path (session, origin checks, limits) with no key. The whole UI (phase 3) is built and tested against them before any key exists.

- **Router:** if the message equals a `user_text` in the loaded fixture conversation, return that event's `route`. Else, if it is in `fixtures/router-cases.json`, return the expected route with confidence 0.9. Otherwise return `too_vague` at 0.9.
- **Reasoner:** return the `output` of the fixture event whose `user_text` matches. For a fixture `failed` event, return an output whose first score is 7, both times, so the repair path fails and a `failed` entry is logged.
- **Clock:** inject `now()` into `app/turn.ts`. In golden-path tests, return each event's `at`, so hashes match `fixtures/rent-or-buy/expected/log.json`.

Scope: the golden-path test (P3.2) replays the main fixture through the UI. The edits fixture is covered at the core and storage level (P1.8, P2.5), because its frame edits, rewinds and accept/dismiss are UI actions, not messages.

## Eval harness

`evals/run.ts` (Node, `pnpm eval`):
1. Loads scenario files from `evals/scenarios/*.json`.
2. Drives `app/turn.ts` headlessly with the real Router and Reasoner, and an in-memory Dexie (`fake-indexeddb`).
3. Checks the expectations and records route accuracy, schema failures before and after repair, invariant failures, guard findings, latency and cost.
4. Writes `evals/reports/<date>-<model>-<prompt versions>.json` plus a one-screen Markdown summary.

Pass bar for release: router accuracy ≥ 90%; no non-applied message routed as applied above 0.7; 0 invariant failures after repair; schema failures before repair < 5%; S01 to S12 all pass.

## Manual check before each phase sign-off

- Run the golden path in all four themes, at desktop width and at 390 px width.
- Keyboard only: send a message, open each panel section, change version, copy.
- Export, then clear local data, then import: the state is identical.
