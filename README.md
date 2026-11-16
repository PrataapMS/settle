<div align="center">

# Settle

**Talk it through. Watch it add up.**

A decision helper that turns a conversation into a clear, auditable decision, with numbers you can trust.

[![CI](https://github.com/PrataapMS/settle/actions/workflows/ci.yml/badge.svg)](https://github.com/PrataapMS/settle/actions/workflows/ci.yml)
![Status](https://img.shields.io/badge/status-in%20development-orange)
![Stack](https://img.shields.io/badge/stack-React%20%C2%B7%20Vite%20%C2%B7%20Cloudflare%20Workers-blue)

</div>

---

## What is Settle?

Big decisions rarely fail for lack of opinions. They fail because the reasoning gets lost: a number someone guessed, a risk nobody checked, a preference that quietly changed.

Settle keeps that reasoning in one place. You describe the decision in plain words on the left. On the right, a **live decision panel** builds up as you talk: the options, what matters to you and how much, the facts that are still missing, the checks each option must pass, and where things stand right now.

```
┌───────────────────────────────┬──────────────────────────────────────────┐
│  Conversation                 │  Decision panel                    v3 ▸  │
│                               │                                          │
│  You: Should I rent or buy    │  Leaning: Rent        Confidence  ▓▓▓▓░  │
│  in Pune? Flat is ₹1.1 Cr...  │  Rent 81  ·  Buy 67   Evidence    72%    │
│                               │                                          │
│  Settle: Here's how I'd frame │  Gates     ✓ stay   ✓ affordability      │
│  it. Two things I still need: │            ✓ reserve  ✗ price-to-rent    │
│  your reserve, and how long   │  Ceiling   Prepare                       │
│  you'll stay...               │  Next 72 h  ☐ get a loan quote  ☐ ...    │
└───────────────────────────────┴──────────────────────────────────────────┘
```

## Why it's different

- **The engine owns the numbers.** The AI proposes judgements and facts. Deterministic code computes every score, total, gate and limit. A confident tone can never raise a number.
- **Only messages that matter change the decision.** "Hmm, okay" doesn't move anything. Settle checks each message first and asks for more when it's vague.
- **Every change is visible.** Each update is a numbered version (v1, v2, v3...) with what changed and why. Go back to any version, or rewind to it.
- **You grade the predictions.** Each turn makes one falsifiable prediction with a check date. You mark whether it held, so Settle's calibration is honest.
- **Private by default.** No account. Your decisions live in your browser, and the server keeps no conversation data.
- **It advises, it never acts.** Nothing commits money or signs anything for you.

## Features

- Conversation and decision panel side by side, resizable; a simple switch on phones
- Weighted option matrix, gates (pass, partial, fail, unknown), evidence strength and an action ceiling
- "Needs answers" list that turns open questions into one-tap prompts
- Version history with rewind, and a tamper-evident log (SHA-256 hash chain)
- Copy as formatted text, Markdown or JSON; export and import a whole decision as one file
- Four themes (Midnight, Light, Dark, Paper) and two densities
- Installable PWA; existing decisions open and export offline
- Keyboard friendly and built to WCAG 2.2 AA

## How it works

```
Browser                                   Cloudflare Worker                 Providers
──────────────────────────────            ──────────────────────────        ──────────────
React app + decision engine   ── /api ──▶ security guards              ──▶  OpenRouter
IndexedDB (your decisions)    same origin   (session, limits, budget)        (reasoning model)
                                            server-side prompts        ──▶  Jev (turn check)
                              ◀──────────── validated, structured reply
```

1. You send a message. The Worker checks whether it moves the decision.
2. If it does, the reasoning model proposes updates as structured data, which the Worker validates against strict schemas.
3. Your browser runs the engine on those proposals, computes every number, and appends the result to an append-only log.
4. The panel re-renders from the new version and shows what changed.

The full design is in [docs/02-architecture.md](docs/02-architecture.md).

## Security and privacy

Settle is built so that there is nothing valuable to steal from the browser and no easy way to run up a bill.

- **No API keys in the browser, ever.** All model calls go through Settle's own Worker; keys are Cloudflare secrets.
- **Abuse protection:** invisible Turnstile challenge, per-session and per-IP rate limits, daily allowances, a global spend cap, and a provider-side credit limit as the last line.
- **Not an open AI proxy:** prompts, schemas, models and token limits are fixed on the server; outputs must pass validation.
- **Strict browser hardening:** a strict Content Security Policy with Trusted Types, no inline scripts, no third-party trackers, and model text rendered as plain text.
- **Privacy:** the server never stores or logs message text, IP addresses are kept only as daily-salted hashes, and requests go only to providers that don't train on your data.

Details and the threat model: [docs/10-security-and-privacy.md](docs/10-security-and-privacy.md). To report a vulnerability, see [SECURITY.md](SECURITY.md).

## Tech stack

| Layer | Choice |
|---|---|
| App | React 19, TypeScript (strict), Vite, PWA |
| UI | shadcn/ui on Tailwind CSS, lucide icons, Lexend and JetBrains Mono (self-hosted) |
| Data | IndexedDB via Dexie, Zustand for UI state, Zod for every boundary |
| Server | Cloudflare Workers (static assets and `/api`), Durable Objects, Rate Limiting, Turnstile |
| AI | OpenRouter (structured outputs), TypeSafe Jev for the turn check |
| Quality | Vitest, Testing Library, Cloudflare's Workers test pool, Playwright with axe, gitleaks, Dependabot |

## Getting started

### Prerequisites

- Node.js 24+ (an `.nvmrc` is included) with Corepack enabled: `corepack enable`
- Python 3.10+ (only for the reference engine and schema tools; no packages needed)
- Optional: `brew install gitleaks` for the local pre-commit secret scan

### Run it

```sh
git clone https://github.com/PrataapMS/settle.git
cd settle
pnpm install
pnpm dev
```

Open http://localhost:5173.

> **Project status:** Settle is being built phase by phase (see the roadmap below). Today `pnpm dev` serves the starter shell. A no-key mock mode (`pnpm dev:mock`) and live mode with your own development key arrive in phase 0.

### Live mode (from phase 0.4)

Copy `.dev.vars.example` to `.dev.vars` and add a development OpenRouter key with a low credit limit. The file is gitignored and is read only by the local Worker; the key never reaches the browser.

## Scripts

| Command | What it does | Available |
|---|---|---|
| `pnpm dev` | Dev server (from P0.4: the Worker runs inside Vite with live models) | now |
| `pnpm build` | Type-check and build for production | now |
| `pnpm typecheck` | TypeScript project check | now |
| `pnpm check:kit` | Reference engine selftest, golden fixture checks, hash vectors | now |
| `pnpm dev:mock` | Dev server with fixture-driven mock models, no keys needed | P0.4 |
| `pnpm lint` | ESLint, including the architecture import rules | P0.3 |
| `pnpm test` | Unit, golden, schema parity, component and Worker security tests | P0.3 |
| `pnpm test:e2e` | Playwright end-to-end flows with axe accessibility checks | P0.3 |
| `pnpm eval` | Router and scenario evals against live models (costs credits) | P6 |

## Project structure

```
settle/
├── src/            the browser app: core engine (pure TS), api client, storage, features, UI
├── worker/         the Cloudflare Worker: /api gateway, security guards, LLM calls   (from P0.4)
├── prompts/        system prompts the Worker sends to the model
├── schemas/        JSON Schemas for structured model output
├── fixtures/       golden conversations and expected states: the engine's spec
├── tools/          reference engine (Python), schema builder, hash checker
├── docs/           product, architecture, engine rules, security, deployment
├── evals/          end-to-end scenarios and reports
└── design/         theme tokens and the approved prototype
```

Start with [docs/README.md](docs/README.md) for a guided index.

## Roadmap

| Phase | Goal | Status |
|---|---|---|
| P0 | Project setup, security baseline, CI, spikes | In progress |
| P1 | Core engine in pure TypeScript, byte-identical to the golden fixtures | Planned |
| P2 | Local storage, export and import, rewind | Planned |
| P3 | Full UI with mock models, four themes, phone and desktop | Planned |
| P4 | Live models through the Worker gateway | Planned |
| P5 | Jev turn check (if it meets the bar) | Planned |
| P6 | Evals, tuning and hardening | Planned |
| P7 | Security review and release on Cloudflare | Planned |

Feature-level detail: [ROADMAP.md](ROADMAP.md).

## Contributing

Work follows [CLAUDE.md](CLAUDE.md), which applies to people and coding agents alike:

- One task per commit, message `P<phase>.<task>: <summary>`.
- Tests first for anything in `src/core`; golden fixtures are the spec and are never edited by hand.
- Rule, schema, prompt or dependency changes are explained in the pull request.
- `pnpm lint`, `pnpm typecheck` and `pnpm test` must be green before merging.

## License

[MIT](LICENSE)
