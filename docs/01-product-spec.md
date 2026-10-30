# 01 · Product spec

## What Settle is

Settle helps one person work through one decision at a time in a conversation. Every message that moves the decision updates a live decision panel: direction, scores, a weighted matrix, gates, next actions and an audit trail. Messages that don't move it are not applied, and the user is asked to say more.

Settle advises. It never acts: there is no "execute" step, and anything that commits money or signs something is left to the user.

## Principles

1. **The engine owns the numbers.** The model proposes judgements and facts; deterministic code computes totals, gates, evidence strength, the action ceiling and every delta. A confident tone can never raise a score.
2. **Only relevant messages change the decision.** A turn check runs first. Vague, off-topic and meta messages are logged but never touch the state.
3. **Every change is visible.** Each decision turn produces a new numbered state version (v1, v2, …). The panel shows what changed and why, and any earlier version can be viewed.
4. **Local and private by default.** No Settle account. Every decision lives in the browser; the server keeps no conversation data. Export is one file.
5. **Readable first.** The panel must be scannable in seconds: headline direction, four score tiles, then collapsible sections.

## Users and scope

- Primary: individuals making personal or work decisions with real stakes (housing, jobs, purchases, technical choices), comfortable typing a few sentences.
- In scope for v1: one user per browser, many decisions, conversation plus panel, four themes, copy and export, OpenRouter models, optional Jev turn check, installable PWA, offline reading of existing decisions.
- Out of scope for v1: accounts and sync, collaboration or sharing links, file and document upload (the `document` evidence source is reserved for v2), voice, mobile apps, automated actions of any kind.

## Core behaviours

### Starting a decision
The user describes the decision. The model proposes a **frame** (options, criteria with weights, required inputs, derived metrics, gates). The panel shows the frame for review: the user can accept it as is, adjust weights, thresholds and required flags, and rename items. Scoring starts from the accepted frame. Adding or removing options or criteria after the first turn isn't in v1; "Start a new decision from this one" covers it. See `03-decision-frame.md`.

### Each later message
1. The turn check classifies the message into one route (`06` and `07` describe routes).
2. Applied routes (adds evidence, changes a preference, challenges the analysis) go to the reasoning model with the current state. The reply is validated, the engine computes, and the state becomes v+1.
3. `meta` messages (including `/commands`) are answered from the state. State unchanged.
4. `too_vague` and `off_topic` messages are not applied. The reply says so, offers the open questions as one-tap starters, and offers "It is relevant: apply it anyway".
5. If the turn check is under 70% confident, Settle asks "Should this update the decision?" with two buttons.

### The panel
Always visible on the right half on desktop; a Conversation / Decision switch on narrow screens. Shows the selected version (latest by default; "Panel follows the latest turn" setting). Content and order are specified in `08-ui-spec.md`.

### Predictions and calibration
Each decision turn registers one falsifiable prediction with a check date (default 72 hours). When it comes due, the thread shows a prompt to grade it: held, did not hold, or too early. Only the user grades. Calibration (held ÷ resolved) appears in the panel and in clearance.

### Copy and export
- Copy (formatted): HTML with headings and tables, plus plain text, for pasting into Docs, Notion or email.
- Markdown and JSON for the selected version.
- Copy thread as Markdown.
- Export decision file (JSON: log, current state, and optionally checklist ticks); import replays the log and verifies the hash chain.

### Themes and density
Midnight (default), Light, Dark, Paper; comfortable or compact density. Preferences persist locally.

## Non-functional requirements

| Area | Requirement |
|---|---|
| Latency | Turn check under 600 ms p95 on Jev, under 1.5 s on the fallback. First reasoning token or progress state under 1 s; full decision turn under 25 s p95. |
| Reliability | Zero invariant failures reach the UI. A failed turn leaves the previous state intact. |
| Accessibility | WCAG 2.2 AA: keyboard reachable, visible focus, 4.5:1 text contrast in all four themes, no colour-only meaning, reduced motion respected. |
| Privacy | No analytics by default. The browser talks only to the app's own origin (and Turnstile). The Worker forwards each turn to OpenRouter or TypeSafe and keeps no message text. |
| Security | No API key in the browser. Public anonymous use is bounded by Turnstile sessions, rate limits and hard spend caps (`10-security-and-privacy.md`). |
| Offline | Existing decisions open and export offline. Sending a message needs a connection. |
| Storage | Works with 100 decisions of 30 turns each without noticeable slowdown. |
