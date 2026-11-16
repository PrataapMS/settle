# Contributing to Settle

Thanks for helping. Settle is maintained by one person, so small, focused changes are the easiest to review and merge.

## Before you start

- **Bugs and ideas:** open an [issue](https://github.com/PrataapMS/settle/issues/new/choose) first. For anything bigger than a small fix, wait for a reply before writing code.
- **Security problems:** don't open an issue. Follow [SECURITY.md](SECURITY.md).
- **Setup:** Node 24+ with Corepack (`corepack enable`), pnpm, Python 3.10+. Then `pnpm install`. See the [README](README.md#getting-started).

## Making a change

1. Fork the repo and branch from `main`. Name the branch after the task, e.g. `p1.3-expression-evaluator` or `fix-gate-label`.
2. Keep commits small, with a short subject and, if useful, a one or two line body.
3. Run the checks locally:

   ```sh
   pnpm lint && pnpm typecheck && pnpm test
   pnpm check:kit   # if you touched the engine, schemas or fixtures
   ```

4. Open a pull request. The title must match one of:

   | Prefix | Use for |
   |---|---|
   | `P<phase>.<task>:` | a roadmap task, e.g. `P1.3: expression evaluator` |
   | `Fix:` | a bug outside a task |
   | `Docs:` | documentation only |
   | `Chore:` / `Deps:` | housekeeping, dependency updates |

   Put `Closes #<issue>` in the body and fill in the checklist.

5. CI (lint, typecheck, tests, build, secret scan, CodeQL, dependency review) must be green. PRs are squash-merged, so the PR title becomes the commit on `main`.

## Rules that keep the numbers trustworthy

- `src/core` is pure: no React, storage, network, clock or randomness.
- The engine computes every number. Model output never sets a score, total or status directly.
- Golden fixtures in `fixtures/*/expected` are the spec and are never edited by hand.
- Every model output is validated with Zod before it's stored.
- Model text is always rendered as text, never as HTML.
- API keys stay in the Worker. The browser only calls same-origin `/api/*`.
- Changing an engine rule, a schema, a public interface or a security control needs a clear explanation in the PR.

The full specs are in [docs/](docs/README.md). [CLAUDE.md](CLAUDE.md) holds the same rules for coding agents.

## Licence

By contributing, you agree that your contributions are licensed under the [MIT licence](LICENSE).
