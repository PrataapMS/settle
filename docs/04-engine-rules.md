# 04 · Engine rules

Everything in this file is deterministic and lives in `src/core`. The executable version is `tools/reference_engine.py`. Where this document and the reference engine disagree, the reference engine is right and this document has a bug.

The TypeScript engine must reproduce `fixtures/*/expected/*.json` exactly. Compare canonical JSON, not "close enough" numbers.

## Numbers

- `round(x, p)` = sign(x) × floor(|x| × 10^p + 0.5) ÷ 10^p (half away from zero). In TS: `Math.sign(x) * Math.floor(Math.abs(x) * 10 ** p + 0.5) / 10 ** p`. Never `toFixed`, and never `Math.round` on negatives.
- Metrics are rounded to 4 places, evidence strength to 2, totals to 0.

## Canonical JSON (for hashing)

RFC 8785 (JCS):
- Object keys sorted by UTF-16 code units. In JS this is plain `Object.keys(o).sort()`.
- No whitespace.
- Strings as `JSON.stringify` writes them.
- Numbers as `JSON.stringify` writes them (ECMAScript shortest round-trip form; `-0` becomes `0`; non-finite numbers are an error).
- `null`, `true` and `false` as themselves.

The reference engine reproduces JavaScript number formatting exactly. `fixtures/canonical-vectors.json` holds 20 test vectors (exponents, `0.1 + 0.2`, 2^53, 2^53 + 2, 2^60, Unicode keys, control characters), and `tools/check_hashes.mjs` re-verifies the vectors and every fixture log hash with Node (`node tools/check_hashes.mjs fixtures/canonical-vectors.json`).

## Weighted totals

For each option: `total = round(Σ(weight × score) ÷ 5, 0)` over the frame's current criteria. Range 20 to 100.

## Inputs, metrics and gates

- An input is **known** when its state entry exists and its value is not null, whatever the source.
- Metrics evaluate in frame order over numeric inputs and earlier metrics (`03-decision-frame.md`). Each is rounded to 4 places before later metrics use it.
- Gate status:
  - `unknown`: the subject's value is null and no `depends_on` input is known.
  - `partial`: the subject's value is null but at least one `depends_on` input is known.
  - `pass` or `fail`: the subject has a value and the comparison holds or fails.
- `is_new` is true for gates added in this version, by an auto-applied proposal or by `frame_accept`. It is false after a rewind.

## Evidence strength

```
required  = frame inputs with required = true
counted   = required inputs that are known and whose source is not "assumed"
weight    = user 0.8, document 1.0
strength  = round(Σ weight(counted) ÷ |required|, 2)     (0 if no inputs are required)
evidence  = {known: |counted|, required: |required|, strength}
```

Assumed values can make a gate evaluable, but they never count as evidence.

## Action ceiling

Ladder: `observe` < `recommend` < `simulate` < `prepare` < `request_warrant`.

```
if record.coherence.level == "low"                    → observe
else if protective gates exist and all pass
        and record.scores.risk ≤ 50
        and record.reality.executable_under_constraints → prepare
else if evidence.known ≥ 3                             → simulate
else                                                   → recommend
```

`request_warrant` is never granted. Each proposed action bound gets a status: `within` when its rung ≤ the ceiling, `above` otherwise, and always `needs_user` for `request_warrant`.

## System confidence and deltas (every version-creating kind, including rewind)

- `system_confidence`: `evolving` on v1; afterwards `stable` if |confidence − previous confidence| < 15, else `evolving`.
- `deltas` (null on v1): `confidence`, `risk`, `evidence_strength` (rounded to 2), `totals` per option, `gates_passed`, `ceiling_steps` (difference in ladder index), `criteria_changed` (ids with a changed score for any option), `gates_changed` (ids whose status changed, including newly added gates).

## Belief

- If the claim equals the previous version's claim, keep `since_v` and `history`.
- Otherwise `since_v = v`, and the previous claim is appended to `history` as `{v: previous since_v, text}`.

## Frame proposals

A record's `frame_proposal` is split:
- **Auto part:** `add_inputs`, `add_metrics` and advisory `add_gates`. Applied in the same turn; the frame gets a new version.
- **Held part:** protective `add_gates` and `change_weights`. Stored as `pending_frame_proposal` until a `frame_accept` or `frame_dismiss` entry. A new held part replaces an earlier one; a proposal with no held part leaves the earlier one in place.
- `frame_edit` is refused while a proposal is pending.

The held part is validated as if applied (invariant `proposal_valid`), so a proposal that could never be accepted is rejected at once and sent to repair.

## Frame versions

`frame_version` identifies frame content. Every applied change (auto part, accept, edit) takes `max(all frame versions so far) + 1`. A rewind restores the earlier frame with its original number. So numbers are never reused for different content, but they are not monotonic over versions.

## Predictions and calibration

- Each decision version adds `{id: "p<v>", made_in: v, text, check_at, status: "open"}`.
- `check_at` = turn time + `check_after_hours`, in UTC, formatted `YYYY-MM-DDTHH:MM:SSZ`. In TS: `new Date(ms).toISOString().replace(/\.\d{3}Z$/, 'Z')`.
- `grade` sets a status to `held`, `missed` or `open`. It updates `predictions` and `calibration` in place; no new version.
- `calibration = {resolved: held + missed, held, missed, graded_by: resolved > 0 ? "user" : "none"}`.

## Invariants (any failure rejects the turn or frame change)

| id | Check |
|---|---|
| `weights_sum_100` | Criteria weights sum to 100 |
| `scores_in_range` | Every matrix score is an integer from 1 to 5 |
| `matrix_complete` | Every criterion appears once, with a score for every option |
| `inputs_in_frame` | Every input id in the record exists in the frame (after the auto part) |
| `input_types_match` | Each value matches its input type: number (finite, not boolean), boolean, or text; null is allowed |
| `option_refs_valid` | Break-condition `option_id`s exist, and are present for `favours_option` and `flips_decision` |
| `scores_0_100` | Confidence and risk are integers from 0 to 100 |
| `no_truncated_text` | `reply`, `claim`, `summary` and `direction` end with `. ! ? ) ” ’ "` |
| `frame_valid` | The frame passes validation (`03-decision-frame.md`) |
| `proposal_valid` | Applying the held proposal would still give a valid frame |

On failure: one repair call with the failed checks as plain-language errors (`prompts/repair.md`). If it still fails, log `{kind: "failed"}` and keep the previous state.

## Log replay

The state is a pure function of the log. `replay(log)` walks entries in `seq` order:

| Kind | New version? | Effect |
|---|---|---|
| `decision` | yes | First entry sets the frame (version 1). Apply the auto part of any proposal, store the held part, check invariants, merge inputs (`since_v` changes only when a value changes), add the prediction, compute. |
| `frame_accept` | yes | Apply the pending proposal, check invariants, recompute from the last record. |
| `frame_dismiss` | no | Clear the pending proposal. |
| `frame_edit` | yes | Refused while a proposal is pending. Apply `changes` (weights, thresholds, protective, required, units, labels), check invariants, recompute from the last record. |
| `rewind` | yes | `to_v` must be an earlier version and not superseded. Restore that version's frame, inputs, record, computed values and pending proposal. Set `cause: "rewind"`, `base_v: to_v`, and `superseded` = previous superseded ∪ {to_v+1 … v−1}. Predictions and calibration stay current. Recompute system confidence and deltas against the version before. |
| `grade` | no | Update predictions and calibration. |
| `meta`, `clarify`, `failed` | no | Only `log_head` moves. `meta` entries carry route `meta`; a `clarify` entry carries an applied route only when `user_choice` is `"comment"`. |

Versions never get renumbered. Superseded versions stay viewable and can't be rewind targets. Every kind except `decision` requires an existing decision: the first entry of a log is always a decision.

Metric expressions are syntax-checked in full when a frame is validated (`check_syntax` in the reference engine), so a frame that would fail later during evaluation can never be logged. `python3 tools/reference_engine.py --selftest` lists the error cases to mirror as TS unit tests.

## Hash chain

- Each log entry gets `seq` (from 1), `decision_id`, `prev_hash` (`"genesis"` for the first entry) and `hash = sha256_hex(canonical(entry without "hash"))`.
- The state carries `log_head` = the hash of the last applied entry.
- Import replays the file's log, recomputes every hash and compares; the first mismatch stops the import and names its `seq`.
