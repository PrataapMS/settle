# Design assets

| Path | What it is |
|---|---|
| `tokens.css` | Theme tokens for shadcn/ui and Tailwind v4: four themes (Midnight, Light, Dark, Paper), section accents, option colours, density. Contrast-checked (all text pairs ≥ 4.5:1). Copy to `src/theme/tokens.css` in P0.2. |
| `prototype/Main.dc.html` | The approved interactive prototype (conversation left, decision panel right). Reference for layout, content order, copy and behaviour. |
| `prototype/Contract.dc.html` | Review board: response contract, defects in the CLEAR output, who does what (Jev, model, engine). |
| `prototype/State.dc.html` | Review board: state, storage and export. |
| `legacy/clear-transparency-output.json` | A CLEAR output, kept to show the field mapping and its defects (`docs/05`). |
| `legacy/clear-state-export.json` | A CLEAR state-token export, kept for comparison (`docs/06`). |

## Viewing the prototype

Open the design canvas in Claude: https://claude.ai/artifact/5RALjCyShKwo1jgntfjXXd (private to you until you share it). The `.dc.html` files need the canvas runtime, so they will not render on their own in a browser. Read them as source: the data and the copy are in the `<script>` block at the bottom of `Main.dc.html`.

## Where the specs supersede the boards

The boards were made for review before the specs were final. When they differ, follow `docs/` and `schemas/`:

- **Hashing:** the State board shows a hash per state. The spec chains **log entries** instead (`docs/04`, Hash chain); the state carries `log_head`.
- **Model output shape:** the Contract board sketches `inputs` as an object and the matrix with `weight`. The schemas use an `inputs` array, and weights live only in the frame (`schemas/record.schema.json`).
- **Evidence numbers:** the prototype counted 8 inputs, so it shows 70% at v3. The frame in the fixtures has 9 required inputs, then 10 after v3's proposal, so it shows **72%**. Follow `fixtures/*/expected`.
- **Visual language:** the prototype uses the Kuat design system. The build uses shadcn/ui with `tokens.css`. Keep the layout, hierarchy and colour roles, not the Kuat components.
- **Turn check:** the prototype fakes routing with keywords. The build uses Jev or the fallback model (`docs/07`).
