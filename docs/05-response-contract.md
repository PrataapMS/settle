# 05 · Response contract

## Who writes what

| Field group | Written by | Where it is validated |
|---|---|---|
| Frame (first turn), frame proposals | Reasoning model | Zod + `validateFrame` |
| Decision record: reply, claim, direction, scores, matrix scores, inputs, stress tests, actions, prediction, coherence | Reasoning model | Zod + invariants |
| Route | Jev, fallback model, or rule (`/commands`) | Zod (`route.schema.json`) |
| Metrics, gate status, totals, evidence, ceiling, bound status, system confidence, deltas, belief history, calibration, hashes | Engine | Golden tests |

The model never sends engine-owned fields. If a future prompt change makes it try, the schema (`additionalProperties: false`) rejects the output.

## Schemas

| File | Sent as `response_format` for | Notes |
|---|---|---|
| `schemas/frame-turn-output.schema.json` | First turn | `{frame, record}` |
| `schemas/decision-turn-output.schema.json` | Applied later turns | `{record}` |
| `schemas/route.schema.json` | Fallback router | `{route, confidence, reason}` |
| `schemas/frame.schema.json`, `schemas/record.schema.json` | (parts, for reference and Zod) | |

The schemas stay inside the strict structured-output subset: every property required, `additionalProperties: false`, nullable fields as `["type", "null"]`, no `minimum`, `maximum`, `minLength` or `maxItems`. Ranges (scores 1 to 5, 0 to 100, weights summing to 100, list lengths) are checked by Zod and the invariants instead.

Regenerate with `python3 tools/build_schemas.py` after editing `tools/build_schemas.py`.

In the app, define the Zod schemas by hand in `src/core/schema/` (with `.min/.max/.int()` refinements for ranges). Add a parity test that converts them to JSON Schema and compares the result structurally with `/schemas`, after normalising both sides:
- remove `description`, `title`, `$schema`, `minimum`, `maximum`, `exclusiveMinimum`, `exclusiveMaximum`, `minItems`, `maxItems`, `minLength` and `maxLength`;
- rewrite `anyOf: [X, {type: "null"}]` as `type: [X.type, "null"]` (and the same for enums with null);
- sort `required` arrays.

Use Zod 4's built-in `z.toJSONSchema()`. The `/schemas` files are what the model sees, so they must not drift; the ranges they omit are enforced by Zod and the invariants.

## Field notes

- `record.inputs` holds only inputs that are new or changed this turn. `value` type must match the frame input's `type`. Money is in the frame's currency units (no lakh or crore strings).
- `record.matrix` covers every criterion and every option on every turn, even when unchanged. That keeps the record self-contained and makes the invariants simple.
- `falsifiability.break_conditions[].effect`: `reduces_confidence`, `increases_confidence`, `favours_option` (needs `option_id`), `flips_decision` (needs `option_id`).
- `action_bounds[].level` uses the ladder ids. The model proposes; the engine marks each one within, above or needs-user.
- `prediction.check_after_hours` defaults to 72; allow 24 to 720.
- `frame_proposal` is null unless the turn proposes a frame change. The engine applies its additive parts (inputs, metrics, advisory gates) at once, and holds weight changes and protective gates for the user (`03-decision-frame.md`). Inputs added in the proposal may be reported in the same record's `inputs`, because additive parts are applied before validation. `change_weights` must keep the total at 100.
- Field meanings the prompts define (`prompts/shared-rules.md`): `status`, `executable_under_constraints`, `coherence.level` (`low` forces the Observe ceiling), `gap_category` and the five `flourishing` fields.
- `stakes_register` is a fixed list (`conversational`, `personal-low`, `personal-financial-high`, `work-high`, `health-safety-high`). `health-safety-high` makes the UI show a "consult a professional" note at the top of the panel.

## Mapping from the CLEAR output

The legacy exports are in `design/legacy/`. How their fields map:

| CLEAR field | Settle |
|---|---|
| `claim` | `record.claim` |
| `vectors.zeta_alignment_vector.direction` | `record.direction` |
| `evidence.{strength,type,basis}` | `record.evidence.{observed,inferred}` + engine `evidence` (strength is computed, not asserted) |
| `key_variables`, `blocking_unknowns` | same names in `record` |
| `risk.{score,irreversibility_window,failure_mode}` | `record.scores.risk` + `record.risk.*` (risk is stored once) |
| `vectors.adversarial` | `record.adversarial` |
| `vectors.flourishing` incl. `next_72h_actions` | `record.flourishing` + `record.next_72h` |
| `vectors.forward_disclosure` | `record.forward_disclosure` |
| `falsifiability.*` | `record.falsifiability.*` |
| `physical_constraints.*` | `record.reality.*` |
| `action_bounds` | `record.action_bounds` (+ engine status) |
| `clearance.*` | engine `ceiling` + `action_bounds[].status` |
| `prediction_review`, `calibration` | engine `predictions`, `calibration` (user-graded) |
| `coherence`, `system_confidence`, `stakes_register` | `record.coherence`, engine `system_confidence`, `record.stakes_register` |
| `state_token` | replaced by the log and its hash chain (`06-state-and-storage.md`) |

The defects this fixes in the CLEAR output: topic bleed after `/transparency`; risk 0.62 in the record against 0.1 in clearance; truncated strings; false-precision evidence strength; calibration that could never move; a ceiling with no basis.
