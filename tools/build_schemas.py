#!/usr/bin/env python3
"""Generates the JSON Schemas in schemas/ from one set of definitions.

Model-facing schemas (frame-turn, decision-turn, route) follow the strict
structured-output subset: every property required, additionalProperties false,
nullable fields as type arrays, no numeric or length constraints (the engine and
Zod enforce ranges instead).

Usage: python3 tools/build_schemas.py
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "schemas"


def obj(props, desc=None):
    o = {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}
    if desc:
        o["description"] = desc
    return o


def s(desc=None):
    return {"type": "string", **({"description": desc} if desc else {})}


def i(desc=None):
    return {"type": "integer", **({"description": desc} if desc else {})}


def n(desc=None):
    return {"type": "number", **({"description": desc} if desc else {})}


def b(desc=None):
    return {"type": "boolean", **({"description": desc} if desc else {})}


def arr(items, desc=None):
    return {"type": "array", "items": items, **({"description": desc} if desc else {})}


def enum(values, desc=None):
    return {"type": "string", "enum": values, **({"description": desc} if desc else {})}


def nullable(schema):
    out = dict(schema)
    out["type"] = [schema["type"], "null"]
    if "enum" in out:
        out["enum"] = out["enum"] + [None]
    return out


LADDER = ["observe", "recommend", "simulate", "prepare", "request_warrant"]
ROUTES = ["new_decision", "adds_evidence", "changes_preference", "challenges_analysis", "meta", "too_vague", "off_topic"]

ID = s("snake_case identifier, unique within its list")

INPUT_DEF = obj({
    "id": ID,
    "label": s("Short label shown in the panel"),
    "type": enum(["number", "boolean", "text"]),
    "unit": s("Unit for display, e.g. 'INR/month', '%', 'years'. Empty string if none."),
    "required": b("True if the decision cannot close without it. Counts towards evidence strength."),
})

METRIC_DEF = obj({
    "id": ID,
    "label": s(),
    "unit": s(),
    "expr": s("Arithmetic over input and earlier metric ids: + - * / ( ), numbers, pmt(rate_pct, years, principal), min(a,b), max(a,b). No other syntax."),
})

GATE_DEF = obj({
    "id": s("Starts with g_"),
    "label": s(),
    "subject": s("An input id or metric id whose value is compared"),
    "op": enum(["<=", ">=", "<", ">", "=="]),
    "threshold": n(),
    "threshold_text": s("The threshold in plain words"),
    "protective": b("Protective gates decide the action ceiling. Advisory gates (false) only inform."),
    "depends_on": arr(s("input id"), "Inputs that feed the subject. Used to report a partial gate."),
})

FRAME = obj({
    "decision_type": s("snake_case kind of decision, e.g. rent_vs_buy_home"),
    "title": s("Short title the user would recognise"),
    "currency": nullable(s("ISO 4217 code if money is involved")),
    "options": arr(obj({"id": ID, "label": s()}), "2 to 5 options"),
    "criteria": arr(obj({"id": ID, "label": s(), "weight": i("Integer weight; all weights sum to 100")}), "3 to 7 criteria"),
    "inputs": arr(INPUT_DEF, "Facts the decision depends on"),
    "metrics": arr(METRIC_DEF, "Derived numbers the engine computes; never compute them yourself"),
    "gates": arr(GATE_DEF, "Thresholds that must hold before stronger actions are allowed"),
}, "The decision frame. Proposed on the first turn; the user confirms it.")

RECORD = obj({
    "status": enum(["partial", "evolving", "ready"]),
    "stakes_register": enum(["conversational", "personal-low", "personal-financial-high", "work-high", "health-safety-high"]),
    "verdict": s("One line, under 15 words"),
    "summary": s("One sentence: what this turn changed"),
    "reply": s("The conversational reply. Paragraphs separated by a blank line. Must end with terminal punctuation."),
    "claim": s("The load-bearing claim the direction rests on. One or two sentences."),
    "direction": s("What to do now, in one or two sentences"),
    "scores": obj({"confidence": i("0-100, confidence in the direction"), "risk": i("0-100, cost of being wrong")}),
    "risk": obj({"irreversibility_window": enum(["reversible", "recoverable_with_cost", "costly", "irreversible"]), "failure_mode": s()}),
    "evidence": obj({"observed": s("Only what the user actually said"), "inferred": s("What you assumed or derived")}),
    "inputs": arr(obj({
        "id": s("Must be an input id in the frame (after any frame_proposal)"),
        "value": {"type": ["number", "boolean", "string", "null"]},
        "source": enum(["user", "document", "assumed"]),
        "note": s("Short provenance note; empty string if none"),
    }), "Only inputs that are new or changed this turn"),
    "matrix": arr(obj({
        "criterion_id": s(),
        "scores": arr(obj({"option_id": s(), "score": i("1-5"), "assumed": b("True if the score rests on an assumption rather than user facts")})),
        "basis": s("Why these scores, in one sentence"),
    }), "Every criterion, every option, every turn"),
    "sensitivity": s("What would make the trailing option overtake"),
    "needs_answers": arr(s("A question that would move the decision"), "1 to 4 questions"),
    "key_variables": arr(s()),
    "blocking_unknowns": arr(s("Must be about this decision")),
    "adversarial": obj({"risk": s(), "exploit_surface": s()}),
    "falsifiability": obj({
        "assumptions": arr(s()),
        "break_conditions": arr(obj({
            "event": s(),
            "effect": enum(["reduces_confidence", "increases_confidence", "favours_option", "flips_decision"]),
            "option_id": nullable(s("Required for favours_option and flips_decision")),
        })),
        "what_would_change_this": s(),
    }),
    "reality": obj({"resists": s(), "resources": s(), "dependencies": s(), "executable_under_constraints": b()}),
    "action_bounds": arr(obj({"level": enum(LADDER), "action": s()}), "Proposed actions; the engine decides which are within the ceiling"),
    "next_72h": arr(s(), "2 to 5 concrete tasks"),
    "flourishing": obj({"direction": s(), "leverage": s(), "stability": s(), "agency_rebalance": s(), "trajectory_shift": s()}),
    "forward_disclosure": obj({"note": s("The single most useful next input"), "gap_category": enum(["evidence", "structure", "preference", "constraint"])}),
    "prediction": obj({"text": s("A falsifiable prediction the user can check"), "check_after_hours": i()}),
    "coherence": obj({"level": enum(["high", "medium", "low"]), "reason": s()}),
    "frame_proposal": nullable({**obj({
        "reason": s(),
        "add_inputs": arr(INPUT_DEF),
        "add_metrics": arr(METRIC_DEF),
        "add_gates": arr(GATE_DEF),
        "change_weights": arr(obj({"criterion_id": s(), "weight": i()})),
    }), "type": "object"}),
    "suggested_followups": arr(s(), "1 to 3 messages the user might send next"),
}, "One decision turn. Never include totals, gate status, evidence strength or the ceiling: the engine computes them.")

ROUTE = obj({
    "route": enum(ROUTES),
    "confidence": n("0-1"),
    "reason": s("One short sentence"),
}, "Turn check output")


def write(name, schema, title):
    schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": title, **schema}
    (OUT / name).write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    OUT.mkdir(exist_ok=True)
    write("frame.schema.json", FRAME, "Settle decision frame")
    write("record.schema.json", RECORD, "Settle decision record (one turn)")
    write("frame-turn-output.schema.json", obj({"frame": FRAME, "record": RECORD}), "Settle model output: first turn of a decision")
    write("decision-turn-output.schema.json", obj({"record": RECORD}), "Settle model output: later decision turns")
    write("route.schema.json", ROUTE, "Settle turn check (router) output")
    print("Wrote schemas to", OUT)


if __name__ == "__main__":
    main()
