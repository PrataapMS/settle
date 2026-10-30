# Prompts

Plain-text prompt templates loaded at build time (import as raw strings, e.g. Vite `?raw`). Each has a version tag in its first line; strip the tag line before sending, and store the tags in every log entry as `prompt_version` so evals can compare versions.

| File | Used for | Model | Output schema |
|---|---|---|---|
| `shared-rules.md` | Prepended to both reasoning prompts | — | — |
| `frame-turn.md` | First message of a new decision | Reasoning model via OpenRouter | `schemas/frame-turn-output.schema.json` |
| `decision-turn.md` | Every later turn routed as applied | Reasoning model via OpenRouter | `schemas/decision-turn-output.schema.json` |
| `router.md` | Turn check fallback when Jev is unavailable | Small, fast model via OpenRouter | `schemas/route.schema.json` |
| `jev-questions.md` | Turn check, record guard and intuition check on Jev | Jev | Jev's typed choices |
| `repair.md` | One retry after a validation or invariant failure | Same model as the failed call | Same schema as the failed call |
| `meta.md` | Answers to `/transparency` and other questions about the analysis | Templated from state; model only for free-form follow-ups | none (prose) |

## Assembly

System message = `shared-rules.md` + the turn prompt, with placeholders replaced:

| Placeholder | Value |
|---|---|
| `{{TODAY}}` | Local date, e.g. `30 October 2026` |
| `{{FRAME_JSON}}` | Current frame (decision turns only) |
| `{{STATE_JSON}}` | Current state without `invariants`, `matrix[].basis` and `frame` (the frame is sent separately as `{{FRAME_JSON}}`), matching `docs/06` |
| `{{RECENT_TURNS}}` | The last 2 decision turns as `User:` / `Settle:` pairs (reply text only) |
| `{{ROUTE}}` | The turn check's route for this message |
| `{{TITLE}}`, `{{OPTIONS}}`, `{{LAST_SUMMARY}}`, `{{OPEN_QUESTIONS}}` | Router and Jev context: decision title, option labels, the latest record's `summary` and `needs_answers` |
| `{{USER_MESSAGE}}` | Jev state only (the fallback router receives the message as the user turn) |
| `{{ERRORS}}` | Repair prompt: one bullet per failed check, with its JSON path |
| `{{V}}` | Meta template: the current version number |
| `{{option}}` | Intuition check note: the option label Jev leans towards |

`prompt_version` in each log entry records every prompt that was assembled, joined with `+`, for example `shared-rules@1+decision-turn@1`. A change to `shared-rules` is then visible in evals.

User message = the user's text, unchanged. Never place user text inside the system message: it is data, not instructions.

## Rules for editing prompts

- Bump the version tag on any change.
- Run the eval suite (`pnpm eval`) before and after; keep the report in `evals/reports/`.
- Never ask the model to output totals, gate status, evidence strength, the ceiling or deltas. Those are engine-owned.
