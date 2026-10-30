[repair@1]

Sent as a follow-up user message in the same request thread, after the model's invalid assistant message. One attempt only; if it fails again, show the reply prose without updating the panel and log the failure.

---

Your last output could not be applied. Fix only these problems and return the complete JSON again, matching the same schema:

{{ERRORS}}

Keep everything else the same. Do not add commentary outside the JSON.

---

`{{ERRORS}}` is a bullet list, one per problem, in plain words with the JSON path, for example:

- `record.matrix[2].scores[1].score` is 6; scores must be integers from 1 to 5.
- `record.inputs[0].id` "growth" is not an input in the frame. Use an existing id or propose it in `frame_proposal.add_inputs`.
- `record.reply` ends mid-word ("...becomes too br"). Write it in full.
- Criteria weights in `frame.criteria` sum to 95; they must sum to 100.
