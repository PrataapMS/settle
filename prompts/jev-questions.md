[jev-questions@1]

Jev takes program state and a set of questions with predefined answer choices, and returns a choice plus a calibrated probability for each question. Confirm the exact request and response shape in TypeSafe's docs during spike S3; the content below is what Settle asks.

## 1. Turn check (every user message)

State passed to Jev:

```
decision_title: {{TITLE}}
options: {{OPTIONS}}
last_summary: {{LAST_SUMMARY}}
open_questions: {{OPEN_QUESTIONS}}
message: {{USER_MESSAGE}}
```

Question `route`: "How should this message be handled for the current decision?"
Choices (key: meaning):
- `adds_evidence`: gives new facts or numbers about this decision
- `changes_preference`: says what matters more or less to the user
- `challenges_analysis`: disputes a number, assumption or conclusion
- `meta`: asks about the analysis without adding facts
- `too_vague`: acknowledgement or hesitation with no content
- `off_topic`: about a different decision or unrelated
- `new_decision`: there is no current decision yet

Use the probability of the top choice as `confidence`. Below 0.7, the app asks the user instead of guessing.

## 2. Record guard (after each validated model reply)

For each item in `blocking_unknowns`, `falsifiability.assumptions` and `reality.*`:

Question: "Is this statement about the decision '{{TITLE}}' between {{OPTIONS}}?"
Choices: `yes`, `no`.

Any `no` above 0.8 is a topic-bleed finding: drop the item, show it in the audit log, and count it in evals. Do not re-call the reasoning model for this.

## 3. Intuition check (optional, behind a setting)

State: the frame, the current inputs and the user's own words from all turns (no matrix scores, no model reply).

Question: "Given only this situation, which option would a sensible person lean towards?"
Choices: each option id, plus `unsure`.

Show the result beside the matrix with its probability. If it disagrees with the matrix leader at 0.7 or above, show: "Intuition leans {{option}}. Is there a factor the matrix is missing?" It never changes scores.
