# 03 · Decision frame

The frame is what lets one engine handle any decision. It says what is being compared and how; the engine never knows the decision is about houses or jobs.

## Contents

| Part | What it is | Rules |
|---|---|---|
| `options` | The alternatives | 2 to 5, unique snake_case ids |
| `criteria` | What makes one option better | 3 to 7, unique ids, non-negative integer weights summing to exactly 100 |
| `inputs` | Facts the decision depends on | `type` number, boolean or text; `required` drives evidence strength; ids unique across inputs and metrics |
| `metrics` | Derived numbers | Expressions over **numeric** inputs and earlier metrics (below); computed only by the engine |
| `gates` | Thresholds on a numeric input or metric | Ids start with `g_`; `protective` gates decide the action ceiling, advisory gates only inform |
| `frame_version` | Integer | Engine-assigned (`04-engine-rules.md`, Frame versions); not part of the model's schema |

Schema for what the model writes: `schemas/frame.schema.json` (no `frame_version`). In Zod, keep two schemas: `FrameDraft` (model output) and `Frame` (`FrameDraft` plus `frame_version`). A full example is the `frame` in `fixtures/rent-or-buy/conversation.json`.

## Metric expressions

Grammar (nothing else is valid):

```
expr       := term (('+' | '-') term)*
term       := factor (('*' | '/') factor)*
factor     := number | identifier | identifier '(' expr (',' expr)* ')' | '(' expr ')' | '-' factor
number     := digits ('.' digits)?
identifier := [a-z_][a-z0-9_]*
functions  := pmt(rate_pct, years, principal) | min(a, b) | max(a, b)
```

- `pmt` is the monthly instalment of an amortising loan: r = rate_pct ÷ 1200, n = years × 12, result = principal × r × (1+r)^n ÷ ((1+r)^n − 1); if r = 0, principal ÷ n; if n ≤ 0, null.
- An identifier must be a **number-type** input or an earlier metric. Boolean and text inputs can't appear in expressions or as gate subjects; use them only in `depends_on`.
- If any referenced value is null, or a division by zero occurs, the metric is null.
- Each metric is rounded to 4 decimal places (half away from zero) before later metrics use it.
- Implement with a hand-written tokenizer and recursive-descent parser. Never use `eval`, `Function` or a general-purpose expression library.

## Gate status

| Situation | Status |
|---|---|
| Subject value is null and no `depends_on` input is known (non-null value, any source) | `unknown` |
| Subject value is null but at least one `depends_on` input is known | `partial` |
| Subject value present and the comparison holds | `pass` |
| Subject value present and the comparison fails | `fail` |

## Validation (engine; reject on failure)

- 2 to 5 options and 3 to 7 criteria, each with unique ids; weights are non-negative integers summing to 100.
- Input and metric ids are unique together.
- Every metric parses, and uses only functions from the list and number-type inputs or earlier metrics.
- Gate ids are unique and start with `g_`. Each `subject` is a number-type input or a metric, `op` is one of `<= >= < > ==`, `threshold` is a number, and every `depends_on` entry is an input id.

## Lifecycle

1. **Proposed:** the first turn returns `{frame, record}`. The UI shows the frame review dialog before the panel fills:
   - options: rename;
   - criteria: weight sliders that keep the sum at 100;
   - inputs: label, unit, a required switch;
   - gates: threshold, a protective switch;
   - metrics: read-only, with the expression shown.
2. **Accepted:** if the user changed anything, append a `frame_edit` right after the first decision entry, so v2 reflects their edits. If they accepted it unchanged, nothing extra is logged.
3. **Proposed changes on later turns** come in `record.frame_proposal`, split by the engine:
   - Applied in the same turn: `add_inputs`, `add_metrics` and advisory `add_gates`.
   - Held for the user: `change_weights` and protective `add_gates`. They are stored as `pending_frame_proposal` and shown as a diff card ("Accept" / "Dismiss"). Accept appends `frame_accept`, which creates a new version recomputed from the last record. Dismiss appends `frame_dismiss`, which clears the pending proposal without a new version. A later turn may propose again; a new held part replaces the old one.
   - The held part must leave a valid frame (weights still summing to 100, so `change_weights` lists every criterion whose weight changes). Otherwise the turn fails `proposal_valid` and goes to repair.
   - A turn whose proposal has only additive parts leaves an existing pending proposal untouched.
   - A rewind restores the version's pending proposal as it was then, even if it was dismissed later. Restoring a version means restoring all of it, so the "Review proposal" banner reappears.
4. **User edits at any time** (panel ⋯ menu → "Edit frame") append `frame_edit` and create a new version. While a proposal is pending, "Edit frame" is disabled with the hint "Accept or dismiss the pending proposal first". That keeps the held weight change valid against the frame it was made for. The edit payload:

   ```json
   {"kind": "frame_edit", "at": "…", "changes": {
     "weights":    [{"criterion_id": "flexibility", "weight": 25}],
     "thresholds": [{"gate_id": "g_afford", "threshold": 0.3}],
     "protective": [{"gate_id": "g_ptr", "protective": true}],
     "required":   [{"input_id": "running_costs_month", "required": true}],
     "units":      [{"input_id": "comparable_rent", "unit": "INR/month"}],
     "labels":     [{"kind": "option|criterion|input|metric|gate", "id": "rent", "label": "Keep renting"}]
   }}
   ```

## Not in v1

Adding or removing an option or a criterion after the first turn. It changes what has to be scored and needs a schema extension (`add_options`, `add_criteria`, `remove_*` with full re-scoring). In v1, the panel ⋯ menu offers "Start a new decision from this one", which seeds a new frame-turn message with the current options and facts. Tracked as a follow-up.

## Starter frames (v1.1)

Ship 3 to 5 frames as JSON in `src/core/frame/starters/` (rent or buy, job offer, major purchase, technology choice). When a new decision matches one, the frame-turn prompt receives it as a suggestion ("Start from this frame and adapt it"). This makes common decisions consistent and cheaper.
