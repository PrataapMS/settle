# 02 · Architecture

## Stack

| Concern | Choice | Notes |
|---|---|---|
| App | React + TypeScript (strict) on Vite, as a PWA | Base project created locally (your PWA starter or `pnpm create vite`) |
| UI | shadcn/ui on Tailwind CSS, lucide-react icons | Components copied into `src/components/ui` by the shadcn CLI |
| Client state | Zustand for UI state; Dexie live queries for data | No global data cache beyond Dexie |
| Storage | IndexedDB via Dexie | Stores: `decisions`, `log`, `ui`, `checks`, `telemetry` (`06-state-and-storage.md`) |
| Validation | Zod | One source for types; JSON Schemas in `/schemas` mirror it for the model |
| Reasoning model | OpenRouter chat completions with `response_format: json_schema` | Model is a setting; default `anthropic/claude-sonnet-5.5` |
| Turn check | Jev (TypeSafe), fallback: small model via OpenRouter | Behind one `Router` interface |
| Hashing | Web Crypto SHA-256 over canonical JSON (RFC 8785 style) | See `04-engine-rules.md` |
| Tests | Vitest (unit, golden), Testing Library (components), Playwright (end to end) | |
| PWA | vite-plugin-pwa | Precache app shell only, never API responses |
| Hosting | Netlify (later) | Static site; optional function for a dev or demo key proxy |

## Module layout

```
src/
  core/                 pure TypeScript, no React, no I/O, no Date.now()
    schema/             Zod schemas: frame, record, route, state, log entry, decision file
    expr/               tokenizer + parser + evaluator for metric expressions
    engine/             computeState(), gates, totals, evidence, ceiling, deltas, invariants
    frame/              validateFrame(), checkSyntax(), splitProposal(), applyProposal(), applyFrameEdit()
    log/                reducer: replay(log) -> states; canonical JSON; hashEntry()
    format/             toMarkdown(), toHtml(), toContractJson() for copy and export
  llm/
    openrouter.ts       fetch wrapper: auth, headers, retries, timeouts, error mapping
    reasoner.ts         buildMessages(), callFrameTurn(), callDecisionTurn(), repair loop
    router/             Router interface, JevRouter, ModelRouter (fallback), ruleRouter (/commands)
    guard.ts            record guard (Jev) — optional
    prompts.ts          imports /prompts/*.md as raw strings and fills placeholders
  store/
    db.ts               Dexie schema and migrations
    repo.ts             appendEntry(), loadDecision(), listDecisions(), exportFile(), importFile()
    settings.ts         theme, density, model, keys, panel sections
  app/
    turn.ts             orchestrates one user message end to end (see sequence below)
  features/
    conversation/       message list, turn cards, clarify card, meta card, composer
    panel/              header, version stepper, tiles, sections, export
    decisions/          sidebar list, new decision, frame review dialog
    settings/           keys (OpenRouter OAuth), model, Jev toggle, data
  components/ui/        shadcn components (generated)
  theme/                tokens.css (from design/tokens.css), ThemeProvider
tests/
  golden/               replays fixtures/rent-or-buy and compares with expected/
  router/               runs fixtures/router-cases.json against a router
evals/                  scenario harness (node script) and reports
```

Dependency rule: `features` → `app` → `llm`, `store`, `core`. `core` imports nothing outside itself. Enforce with an ESLint `no-restricted-imports` rule.

## One user message, end to end

Every user message ends in exactly one log entry (or none, before a decision exists). Nothing is written until the outcome is known, so a failed call never leaves half a turn.

```
composer.send(text)
  └─ app/turn.ts
       A. No current decision (new thread):
            route = router.classify(text, {noDecision: true})        // new_decision | too_vague
            too_vague  → UI-only reply: "Tell me what you're deciding between…"; nothing logged; done
            new_decision → reasoner.frameTurn(text) → validate (B5–B6)
                           still failing after repair → UI-only error card with Retry; no decision row, nothing logged; done
                           → show the frame review dialog
                           → on confirm: create the decision row; append {kind:"decision", …} (+ {kind:"frame_edit"} if edited); done
                           → on cancel: nothing logged
       B. Existing decision:
         1. if text starts with "/" → ruleRouter(text):
              /rewind vN → confirm dialog → append {kind:"rewind", to_v:N}; done
              other /commands → templated meta answer → append {kind:"meta", route:{route:"meta", source:"rule"}}; done
            else route = router.classify(text, context)               // Jev, else fallback model
         2. route = meta            → answer (template or meta-answer prompt, read-only) → append {kind:"meta"}; done
            route = too_vague | off_topic → append {kind:"clarify"}; render the clarify card; done
            route applied, confidence < 0.7 → render "Should this update the decision?":
                 "Yes, apply it" → continue at 3 with route.source = "user"
                 "No, just a comment" → append {kind:"clarify", route, user_choice:"comment"}; done
         3. messages = buildMessages(frame, state, recentTurns, route, text)
         4. output = reasoner.decisionTurn(...)                       // OpenRouter, structured output
         5. Zod parse; on failure → one repair call (prompts/repair.md)
         6. invariants(frameAfterAutoPart, record, heldPart); on failure → one repair call (if not already used)
            still failing → append {kind:"failed", user_text, route, reason}; show the prose muted; done
         7. guard (optional, Jev): drop off-topic items; keep findings
         8. append {kind:"decision", user_text, route, model, prompt_version, output, guard_findings?, override_of?}
         9. state = replay(log) (incrementally: apply the new entry to the cached state); cache on decisions.state
        10. UI re-renders from the Dexie live query; the panel shows v+1 with deltas; focus moves to the new turn card

  Override from a clarify card ("It is relevant: apply it anyway"):
       run B3–B10 with route = {route: "adds_evidence", confidence: 1, source: "user"} and override_of = <seq of the clarify entry>
```

Logged routes are `{route, confidence, source}`. The router's `reason` is shown in the UI tooltip but dropped before logging, so it never affects hashes.

## Key interfaces (TypeScript)

```ts
interface Router { classify(text: string, ctx: RouteContext, signal?: AbortSignal): Promise<RouteResult>; }
type RouteResult = { route: Route; confidence: number; reason: string; source: 'jev' | 'model' | 'rule' };

interface Reasoner {
  frameTurn(text: string, opts: CallOpts): Promise<FrameTurnOutput>;
  decisionTurn(text: string, frame: Frame, state: State, recent: TurnPair[], route: Route, opts: CallOpts): Promise<DecisionTurnOutput>;
}

// core (pure); mirrors tools/reference_engine.py
function computeState(input: {
  frame: Frame; inputs: InputsState; record: DecisionRecord; prev: State | null;
  v: number; at: string; predictions: Prediction[]; newGateIds: Set<string>;
  cause?: 'decision' | 'frame_accept' | 'frame_edit'; baseV?: number | null;
}): State;   // belief is derived from prev; decision_id, title, frame, pending_frame_proposal, invariants and log_head are added by replay
function replay(log: LogEntry[]): { states: State[]; current: State | null };
function appendEntry(log: LogEntry[], partial: NewEntry): Promise<LogEntry>;   // assigns seq, prev_hash, hash
function verifyChain(log: LogEntry[]): Promise<{ ok: true } | { ok: false; seq: number }>;
```

## Error handling

| Failure | Behaviour |
|---|---|
| No key / key revoked | Composer disabled with "Connect OpenRouter" button |
| 401/402 from OpenRouter | Toast with the reason; key settings opened; no log entry |
| 429 / 5xx | Retry twice with backoff (1 s, 3 s), then a retry button on the pending turn |
| Timeout (45 s) | Abort; retry button |
| Schema or invariant failure after repair | Show the reply prose in a muted card marked "Not applied: the analysis did not pass checks", with a Retry button; log `{kind:"failed", reason}` |
| Jev unavailable | Fall back to the model router silently; record `source: "model"` |
| Import hash mismatch | Refuse the import; name the first bad sequence number |
