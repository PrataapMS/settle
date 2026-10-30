[frame-turn@1]

This is the first message of a new decision. Produce two things: a decision frame and the first decision record. Return JSON matching the schema exactly.

The frame
- `options`: the real alternatives the user is choosing between, 2 to 5. Include "keep the status quo" only if it is a genuine option.
- `criteria`: 3 to 7 things that make one option better than another, with integer weights that sum to exactly 100. Weight what matters for this kind of decision; you can refine weights later only with the user's agreement.
- `inputs`: the facts the decision depends on. Mark `required: true` for facts without which the decision cannot responsibly close; these drive evidence strength. Use units the user would recognise and the user's currency.
- `metrics`: derived numbers the engine should compute from inputs, written as expressions over number-type input ids and earlier metric ids. Allowed syntax: numbers, + - * / and parentheses, and the functions pmt(rate_pct, years, principal), min(a, b), max(a, b). Nothing else. Every identifier must be defined above it. Boolean and text inputs cannot appear in expressions.
- `gates`: thresholds that must hold before stronger actions are allowed. A protective gate guards against a costly or irreversible mistake (affordability, safety, time horizon). An advisory gate informs but cannot block. Each gate id starts with `g_`, compares one number-type input or metric (`subject`) with a numeric threshold, and lists the inputs that feed it in `depends_on` (boolean inputs may appear there).
- Prefer few, well-chosen elements: 2 to 3 options, 3 to 5 criteria, up to 12 inputs, up to 6 metrics, 2 to 5 gates.

The first record
- Fill every field of the record as described in the shared rules.
- `inputs`: include anything the user already stated in their first message; otherwise an empty list.
- `frame_proposal`: null on this turn.
- `status`: `partial` unless the first message already contains enough facts to evaluate the protective gates.
- `suggested_followups`: messages that answer the most important open question, written as the user would say them.

The user's first message follows.
