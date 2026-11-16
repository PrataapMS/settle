# Settle roadmap

What's planned, in the order it will be built. Progress is tracked in the [issues](https://github.com/PrataapMS/settle/issues) (one per task, grouped under a phase epic) and the [milestones](https://github.com/PrataapMS/settle/milestones).

Status: ✅ done · 🚧 in progress · ⏳ planned

## P0 · Setup and spikes 🚧

The foundation: a secure place to run the app, and answers to the riskiest questions before building on them.

- ✅ Project scaffold: React, TypeScript and Vite
- ✅ CI, CodeQL, secret scanning and Dependabot on every change
- ✅ Public repository with protected `main` and release tags
- ⏳ Themed UI kit: four themes (Midnight, Light, Dark, Paper)
- ⏳ Lint, unit and end-to-end test tooling
- ⏳ Cloudflare Worker serving the app with a strict security baseline
- ⏳ Sessions, rate limits and daily budgets for AI calls
- ⏳ Spikes: reliable structured output, the gateway on staging, a fast turn checker

## P1 · Decision engine ⏳

The pure TypeScript engine that owns every number, so a confident tone can never move a score.

- Scores, totals, gates, evidence strength and the action ceiling
- A safe formula language for metrics such as EMI or price-to-rent
- Checks every AI turn must pass before it counts
- An append-only log with a tamper-evident hash chain
- Copy a decision as Markdown or formatted HTML

## P2 · Your data, on your device ⏳

- Decisions saved in your browser (IndexedDB), no account needed
- Export and import a decision as one verified file
- Rewind to any earlier version without losing history
- Settings and checklists that persist

## P3 · The full app, with a demo model ⏳

Everything works end to end against a built-in mock model, so you can try Settle with no keys.

- Conversation on the left, live decision panel on the right; a switch on phones
- Direction, scores, open questions, the scoring matrix and gates
- What changed, the next 72 hours, stress tests and long-term wellbeing
- Predictions you grade later, so Settle's calibration stays honest
- Review and edit the decision frame before it's applied
- Keyboard friendly, WCAG 2.2 AA, desktop and phone

## P4 · Live AI ⏳

- Real conversations through Settle's own server; no key ever reaches your browser
- Every AI reply validated against strict schemas, with one repair attempt
- Messages that don't move the decision never change it
- Slash commands, usage meters and clear limit messages

## P5 · Faster turn checks ⏳

- A fast, low-cost model decides whether each message moves the decision, with automatic fallback
- A guard that keeps off-topic content out of the record
- An optional intuition check that never changes scores

## P6 · Evals and polish ⏳

- Twelve end-to-end scenarios that must pass before release
- Installable PWA: open and export your decisions offline
- Prediction reminders and starter templates for common decisions
- Fast with hundreds of decisions; graceful empty and edge states

## P7 · Release ⏳

- Security and privacy review against the threat model
- **v1.0.0** live on Cloudflare

## Releases

- `v0.x` versions are pre-releases: notes on GitHub, nothing deployed.
- A major version (`v1.0.0`, `v2.0.0`, …) is what goes live, after a final manual approval.
- Minor and patch versions after v1 publish release notes; they go live with the next major version.

Have an idea that isn't here? [Open an issue](https://github.com/PrataapMS/settle/issues/new/choose).
