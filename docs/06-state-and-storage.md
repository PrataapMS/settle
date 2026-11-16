# 06 · State and storage

## Model

- **Log (authoritative):** append-only entries per decision, hash-chained. Never edited or deleted, except by deleting the whole decision.
- **State (derived):** `replay(log)` produces it. It is cached on the decision row for fast loading and is rebuilt whenever its `log_head` doesn't match the last entry's hash.
- **Version (`v`):** increments on every change to the analysis: decision turns, frame accept or edit, and rewind. Meta, clarify, failed, grade and frame-dismiss entries don't create versions.

Examples of the exact shapes: `fixtures/rent-or-buy/expected/log.json`, `state-v1.json` … `final-state.json`.

## Log entry

```ts
type LogEntry = {
  seq: number;                 // 1, 2, 3 … per decision
  decision_id: string;
  kind: 'decision' | 'meta' | 'clarify' | 'failed' | 'grade' | 'frame_accept' | 'frame_dismiss' | 'frame_edit' | 'rewind';
  at: string;                  // ISO 8601 with offset, local time of the user
  prev_hash: string;           // 'genesis' for seq 1
  hash: string;                // sha256 hex of canonical(entry without hash)
  // kind-specific:
  user_text?: string;
  route?: { route: Route; confidence: number; source: 'jev' | 'model' | 'rule' | 'user' };  // 'user' = "apply it anyway" or the low-confidence prompt; the router's `reason` is not logged
  override_of?: number;        // seq of the clarify entry the user overrode
  model?: string;              // e.g. 'anthropic/claude-sonnet-5.5'
  prompt_version?: string;     // every prompt assembled, joined with '+', e.g. 'shared-rules@1+decision-turn@1'
  output?: FrameTurnOutput | DecisionTurnOutput;   // after the record guard removed any off-topic items
  guard_findings?: { path: string; text: string; probability: number }[];   // decision, if the guard ran
  user_choice?: 'comment';     // clarify: the user answered "No, just a comment" to the low-confidence prompt
  reason?: string;             // failed
  prediction_id?: string; status?: 'held' | 'missed' | 'open';   // grade
  changes?: FrameEditChanges;  // frame_edit
  to_v?: number;               // rewind
};
```

Keep raw model responses out of the log. Store the validated `output` only, plus token usage and latency in a separate `telemetry` table if you want them. Telemetry is local and is not exported unless the user ticks "Include diagnostics".

## State

Top-level fields (see `state-v3.json` for a full example): `format`, `version`, `decision_id`, `title`, `v`, `cause`, `base_v`, `superseded`, `frame_version`, `frame`, `pending_frame_proposal`, `updated_at`, `status`, `verdict`, `summary`, `direction`, `belief`, `inputs`, `metrics`, `scores`, `risk`, `matrix`, `totals`, `gates`, `evidence`, `assumptions`, `predictions`, `calibration`, `ceiling`, `action_bounds`, `system_confidence`, `coherence`, `deltas`, `invariants`, `log_head`.

The panel reads prose fields (reply, needs answers, stress tests, next 72 hours, flourishing) from the record of the version's decision entry, and computed fields from the state. Write one selector, `selectVersionView(log, v)`, that returns both.

What the model receives each turn (`{{STATE_JSON}}`): the state minus `invariants`, `matrix[].basis` and `frame` (sent separately as `{{FRAME_JSON}}`).

## Dexie schema

```ts
db.version(1).stores({
  decisions: 'id, updated_at, title',          // { id, title, created_at, updated_at, state (cache), archived }
  log: '[decision_id+seq], decision_id, kind',  // LogEntry
  ui: 'key',                                    // { key: 'settings', theme, density, follow_latest, open_sections, model, jev_enabled, ... }
  telemetry: '++id, decision_id, at',           // optional diagnostics
  checks: '[decision_id+v+i]'                   // next-72h checklist ticks (UI-only, not part of the decision log)
});
```

Write a decision turn in one Dexie transaction: append the entry, then update `decisions.state` and `updated_at`. If the transaction fails, nothing changes.

Keys: there are none in the browser. Model and Jev calls go through the Worker (`07`, Where calls run). The session cookie is `HttpOnly`, so scripts never see it, and nothing about it is stored in IndexedDB or exported.

## Rewind

`/rewind vN` (handled by the rule router; it is not a meta turn) or the panel's version menu → "Restore this version". It asks for confirmation, then appends `{kind: "rewind", to_v: N}`, which creates a new version equal to vN. The next decision turn builds on it. Superseded versions stay viewable, marked "Superseded", and can't be restored again; restore a later copy instead.

## Export file

```json
{
  "format": "settle-decision",
  "version": 1,
  "exported_at": "2026-10-30T12:00:00Z",
  "app_version": "0.1.0",
  "decision": {"id": "dec_…", "title": "…", "created_at": "…"},
  "log": [ /* LogEntry[] in seq order */ ],
  "state": { /* current state, for convenience; never trusted on import */ },
  "checks": [ /* optional checklist ticks */ ]
}
```

Import steps:
1. Validate `format` and `version` with Zod, and cap the size at 5 MB.
2. Replay the log while recomputing every hash; refuse on the first mismatch, naming its `seq`.
3. The file's `state` is never trusted. Compare it with the replayed state only to warn that the engine version changed.
4. If a decision with the same `decision.id` already exists, ask "Replace" or "Cancel". There is no "keep both" in v1: `decision_id` is inside every hashed entry, so re-keying would break the chain.

`checks` (checklist ticks) and `ui` settings are not part of the decision file, except `checks` for that decision when the user ticks "Include checklist" on export.

## Migrations

- `version` fields on state, log entry and export file. Increase them on any breaking change, and add a `migrate_vN_to_vN+1` function in `src/store/migrations.ts`.
- Changing engine rules changes computed states, but never the log. After an engine change, states are simply recomputed. Golden fixtures must be regenerated with the reference engine in the same commit, and the rule change explained in the pull request.
