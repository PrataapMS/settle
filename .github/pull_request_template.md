<!-- Title: P<phase>.<task>: <summary>  (or S<n>:, Fix:, Docs:, Chore:, Deps:, Release:) -->

Closes #

## What changed

## Acceptance criteria

<!-- Copy the AC from the issue and tick each one, or say why it is deferred. -->

- [ ]

## Definition of done

- [ ] `pnpm lint`, `pnpm typecheck` and `pnpm test` green (`pnpm test:e2e` from P3; `pnpm check:kit` if fixtures, schemas or the engine changed)
- [ ] New behaviour has tests (written first for `src/core`)
- [ ] UI: checked in all four themes at desktop width and at 390 px (or n/a)
- [ ] `/api`: Worker tests cover the security paths (or n/a)
- [ ] No secrets, no `console.log`, no unused exports
- [ ] Deferred work has a follow-up issue (or n/a)
- [ ] Rule, schema, interface or security control changes explained above (or n/a)
