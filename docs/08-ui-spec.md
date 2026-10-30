# 08 · UI spec (shadcn/ui)

The approved prototype is on the design canvas (link in `design/README.md`); its source is in `design/prototype/` for reference. Match its layout, content order and behaviour. Its visual language moves from Kuat to shadcn/ui with the tokens in `design/tokens.css`.

## Layout

```
┌──────────────────────────── header (60px) ──────────────────────────────┐
│ ☰  [logo] Settle │ Decision title · meta      theme swatches  Compact  Copy thread │
├─────────────── conversation (50%) ──────────┬──────── decision panel (50%) ─────────┤
│ messages (scroll)                           │ sticky panel header                   │
│                                             │ panel body (scroll)                   │
│ composer (pinned bottom)                    │                                       │
└─────────────────────────────────────────────┴───────────────────────────────────────┘
```

- Desktop (≥ 1024 px): `ResizablePanelGroup` horizontal, default 50/50, each side at least 35%. Remember the split in `ui` settings. Both sides scroll independently; the page itself does not scroll.
- Tablet and phone (< 1024 px): one column with a sticky segmented control, "Conversation | Decision · vN". Choosing "Show in panel" on a turn card switches to Decision.
- Decisions list: a left `Sheet` opened from ☰ on all sizes (the prototype's rail). It shows "New decision", decisions sorted by `updated_at` (title, `vN`, status), "Panel follows the latest turn" switch, and "Clear local data".

## shadcn components used

`button`, `textarea`, `badge`, `card`, `accordion`, `table`, `progress`, `toggle-group`, `checkbox`, `switch`, `separator`, `scroll-area`, `resizable`, `sheet`, `dialog`, `alert`, `alert-dialog`, `tooltip`, `dropdown-menu`, `sonner` (toasts), `skeleton`, `slider` (frame weights), `input`, `label`, `tabs` (export Markdown/JSON). Icons: lucide-react.

## Conversation column

| Element | Content | Notes |
|---|---|---|
| User bubble | "You · turn N · time" eyebrow, text | Right aligned, max 82% width; mono font for `/commands` |
| Reply card | Reply paragraphs | Left, with the Settle mark avatar |
| Decision update card | Eyebrow "Decision update · turn N", status badge, "Turn check: route · 92%", verdict (semibold), one row: Confidence x% (delta), Risk x% (delta), Rent n · Buy n, Ceiling; summary; "Show in panel" toggle button (pressed when selected) | Below every applied reply |
| Clarify card | "Not applied" (warning colour), route tag, "State stays vN"; the open questions as full-width buttons (prefill the composer with `On "question": `); link "It is relevant: apply it anyway" | Dashed border; the override runs a decision turn with route `{route: "adds_evidence", confidence: 1, source: "user"}` and `override_of` = the clarify entry's seq (`02-architecture.md`) |
| Meta card | "Meta turn · Decision state unchanged · vN", route tag, buttons: Assumptions, Clearance, Break conditions, What changed, Predictions, Decision state (each opens and scrolls to the panel section) | |
| Low-confidence prompt | "Should this update the decision?" with buttons "Yes, apply it" and "No, just a comment" | Shown when an applied route has confidence < 0.7. Yes runs the decision turn with `source: "user"`; No logs `clarify` with `user_choice: "comment"` |
| Failed card | Muted reply prose with "Not applied: the analysis did not pass checks. Retry" | |
| Pending | User bubble, then a skeleton card with progress text: "Checking the message…", "Reasoning…", "Validating…" | `aria-live="polite"` |
| Due prediction | Inline card when a prediction passes `check_at`: text plus Held / Did not hold / Too early | Once per prediction |

Composer: `Textarea` (3 rows, grows to 8), Send button (`size="lg"`), suggestion chips above (the latest record's `suggested_followups`, plus `/transparency` when no meta turn exists at this version), helper text: "Enter to send, Shift+Enter for a new line. Messages that don't move the decision are not applied." Disabled with a "Connect OpenRouter" button when no key is set.

## Decision panel

### Sticky header
1. Row: eyebrow "Decision state vN", status badge, tags: stakes register, "System confidence: Stable/Evolving", "Coherence: High", "Updated just now" (after a new version, until another version is selected).
2. Row: version stepper (`ToggleGroup` with v1…vN; superseded versions are shown struck through with a tooltip), timestamp; right side: Copy (formatted), Markdown, JSON (`button variant="outline" size="sm"`).
3. Banners when relevant: viewing an older version ("Return to latest"), last message not applied ("See what would help"), pending frame proposal ("Review proposal"; while it shows, "Edit frame" is disabled), health or safety stakes ("Consult a professional").
4. Progress bar while a turn is running.

### Body (top to bottom)
1. **Direction box** (accent: direction): direction (17px semibold), "Load-bearing claim" with the claim, tags "Evidence: self-report" and "Belief held since vN".
2. **Score tiles** (4, grid, wraps): Confidence, Risk (sub: irreversibility window), Evidence strength (sub: known of required inputs), Protective gates (sub: ceiling). Each has a value, a `Progress` bar, and a delta in words ("Up 26 pts", "No change") plus "vs vN−1".
3. **Accordion** (`type="multiple"`, open state persisted):

| Section | Default | Content |
|---|---|---|
| Needs answers before this closes | open | Numbered questions, each with an "Answer" link that fills the composer; two boxes: Key variables, Blocking unknowns |
| Decision matrix | open | Option legend; `Table` with columns Criterion, Weight, one per option (5 dot bars + "4/5" + change tag "+2" + "est." if assumed), Basis; footer row "Weighted score" with deltas; Sensitivity box |
| Gates | open | `Table`: Gate (+ New, Advisory tags), Threshold, Status badge (Pass, Fail, Partial, Unknown, each with an icon), Value with unit; note on protective versus advisory |
| What changed this turn | open | Belief updated box (struck previous claim, new claim); `Table` Measure / vN−1 / vN / Change; prediction review of the previous version; Observed and Inferred boxes |
| Next 72 hours | open | Checkboxes (persisted per version), and a "Would sharpen this analysis" box with a gap-category tag |
| Clearance | open | 5-step ladder (allowed, ceiling, locked, "you decide"); `Table` Rung / Action / Status; basis list (evidence, risk, calibration, executable, invariants); invariant checks list; note "No execute rung: Settle advises; you act." |
| Stress tests and assumptions | closed | Failure mode box with irreversibility tag; Adversarial (risk, exploit surface); Falsifiability (assumptions, break conditions with effect tags, would change this); Reality (resists, resources, dependencies, executable) |
| Flourishing | closed | Definition list of the 5 fields |
| Predictions and calibration | closed | One card per prediction: version, check date, status tag, Held / Did not hold / Too early; calibration line |
| Decision state | closed | Chain status tag ("Chain intact · N entries"), inputs `Table` (input, value with unit, known since vN, source), belief history, state JSON in a scrollable `pre`, buttons Copy state, Export decision file, Import |
| Trajectory across the thread | open | `Table` per version: v, cause, verdict, confidence, risk, totals, ceiling; selected row highlighted; superseded rows struck |
| Export | closed | `Tabs` Markdown / JSON with `pre` and copy buttons; explanation of formatted copy |

4. Footer: "Partial view by design: this panel is the validated decision state. The model's private reasoning is neither stored nor shown." plus Expand all and Collapse all.

### Frame review dialog (first turn and "Edit frame")
`Dialog` with sections: Options (rename), Criteria (`Slider` per weight; the total shows "100 of 100" and Confirm stays disabled until the total is 100), Inputs (label, unit, required switch), Gates (threshold input, protective switch), Metrics (read-only expression in mono). Buttons: "Start with this frame" / "Save changes". Pending proposals open the same dialog in diff mode, with additions and changed weights highlighted, and the buttons "Accept" (`frame_accept`) and "Dismiss" (`frame_dismiss`). The panel ⋯ menu also offers "Start a new decision from this one" (adding or removing options and criteria isn't supported in v1).

## Themes

Four themes from `design/tokens.css`: `midnight` (default), `light`, `dark`, `paper`. Apply as a class on `<html>` (`theme-midnight`, …). Shadcn's tokens (`--background`, `--card`, `--primary`, …) come from the theme; Settle adds section accents (`--sec-*`), option colours (`--opt-a…e`) and delta colours (`--up`, `--down`). Theme swatches in the header are a `ToggleGroup` with `aria-label`s. Density "compact" reduces section padding (`--pad` 20 → 14 px) and base font size (15 → 14 px).

Contrast: every text/background pair must pass 4.5:1 in all four themes, including 11–12 px mono eyebrows. The Playwright suite runs axe in each theme.

## Copy formats

- **Copy (formatted):** `ClipboardItem` with `text/html` (headings, tables with inline borders) and `text/plain` (the Markdown). Fallback: `writeText(markdown)`. On failure, a toast says "Clipboard blocked" and the Export section opens.
- **Markdown:** `core/format/toMarkdown(view)`; example output in `fixtures/rent-or-buy/expected/` can be added as a golden snapshot once implemented.
- **JSON:** the version's record plus the computed state fields (contract view).
- **Copy thread as Markdown:** title, then for each version the user message, the reply and the version's Markdown, separated by `---`.

## Accessibility

- Accordion triggers are buttons with `aria-expanded`; the version stepper is a `ToggleGroup` labelled "Show decision state after turn"; status badges always include text and an icon; deltas always use words, never only colour.
- Focus moves to the new turn card after a decision turn completes, and to the clarify card after a non-applied message. Announce through `aria-live`.
- Every interactive target is at least 44 × 44 px on touch. Respect `prefers-reduced-motion`.
