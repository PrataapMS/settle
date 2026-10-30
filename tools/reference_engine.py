#!/usr/bin/env python3
"""Settle reference engine.

An executable specification of docs/04-engine-rules.md. The TypeScript engine in
src/core must produce identical canonical JSON (and therefore identical hashes)
for the same input log.

Usage:
    python3 tools/reference_engine.py <conversation.json> <expected-dir>           # write expected files
    python3 tools/reference_engine.py --check <conversation.json> <expected-dir>   # verify they are current
    python3 tools/reference_engine.py --vectors fixtures/canonical-vectors.json    # write canonical JSON test vectors
    python3 tools/reference_engine.py --selftest                                   # parser, validation and invariant error cases

No third-party packages. Python 3.10+.
"""
import copy
import hashlib
import json
import math
import re
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

LADDER = ["observe", "recommend", "simulate", "prepare", "request_warrant"]
SOURCE_WEIGHT = {"user": 0.8, "document": 1.0, "assumed": 0.0}
APPLIED_ROUTES = {"new_decision", "adds_evidence", "changes_preference", "challenges_analysis"}
TERMINAL = tuple(".!?)”’\"")
OPS = ("<=", ">=", "<", ">", "==")


# ---------- numbers and canonical JSON (RFC 8785 / ECMAScript rules) ----------

def round_to(x, places):
    """Round half away from zero. TS: Math.sign(x) * Math.floor(Math.abs(x) * 10 ** p + 0.5) / 10 ** p"""
    if x is None:
        return None
    f = 10 ** places
    return normalize_number(math.copysign(math.floor(abs(x) * f + 0.5) / f, x))


def normalize_number(x):
    if isinstance(x, bool) or x is None or isinstance(x, int):
        return x
    if x == 0:
        return 0
    if x.is_integer() and abs(x) <= 2 ** 53:
        return int(x)
    return x


def normalize(obj):
    if isinstance(obj, dict):
        return {k: normalize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [normalize(v) for v in obj]
    if isinstance(obj, float):
        return normalize_number(obj)
    return obj


def js_number(x):
    """Number serialisation exactly as ECMAScript Number.prototype.toString / JSON.stringify."""
    if isinstance(x, bool):
        raise TypeError("bool is not a number")
    if isinstance(x, int) and abs(x) <= 2 ** 53:
        return str(x)
    x = float(x)  # beyond 2^53 JavaScript only has the nearest double
    if not math.isfinite(x):
        raise ValueError("non-finite numbers are not valid JSON")
    if x == 0:
        return "0"
    sign = "-" if x < 0 else ""
    d = Decimal(repr(abs(x)))
    digits = "".join(map(str, d.as_tuple().digits))
    exp = d.as_tuple().exponent
    stripped = digits.rstrip("0")
    exp += len(digits) - len(stripped)
    digits = stripped.lstrip("0") or "0"
    k = len(digits)
    n = k + exp  # value = 0.digits × 10^n
    if k <= n <= 21:
        s = digits + "0" * (n - k)
    elif 0 < n <= 21:
        s = digits[:n] + "." + digits[n:]
    elif -6 < n <= 0:
        s = "0." + "0" * (-n) + digits
    else:
        e = n - 1
        es = ("+" if e >= 0 else "-") + str(abs(e))
        s = digits + "e" + es if k == 1 else digits[0] + "." + digits[1:] + "e" + es
    return sign + s


def canonical(obj):
    """RFC 8785 (JCS): keys sorted by UTF-16 code units, no whitespace, ECMAScript number and string serialisation."""
    if obj is None:
        return "null"
    if obj is True:
        return "true"
    if obj is False:
        return "false"
    if isinstance(obj, (int, float)):
        return js_number(normalize_number(obj))
    if isinstance(obj, str):
        return json.dumps(obj, ensure_ascii=False)
    if isinstance(obj, list):
        return "[" + ",".join(canonical(v) for v in obj) + "]"
    if isinstance(obj, dict):
        keys = sorted(obj.keys(), key=lambda k: k.encode("utf-16-be"))
        return "{" + ",".join(json.dumps(k, ensure_ascii=False) + ":" + canonical(obj[k]) for k in keys) + "}"
    raise TypeError(f"Cannot serialise {type(obj)}")


def sha256(obj):
    return hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()


def utc_iso(at, add_hours=0):
    dt = datetime.fromisoformat(at) + timedelta(hours=add_hours)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------- expression evaluator ----------

TOKEN = re.compile(r"\s*(?:(\d+(?:\.\d+)?)|([a-z_][a-z0-9_]*)|(.))")
FUNCS = {"pmt": 3, "min": 2, "max": 2}


class Null(Exception):
    """A referenced value is null, or a division by zero occurred; the expression is null."""


def tokenize(expr):
    out = []
    for num, name, op in TOKEN.findall(expr):
        if num:
            out.append(("num", float(num)))
        elif name:
            out.append(("id", name))
        elif op.strip():
            if op not in "+-*/(),":
                raise ValueError(f"unexpected character {op!r}")
            out.append(("op", op))
    return out


def identifiers(expr):
    toks = tokenize(expr)
    return {t[1] for i, t in enumerate(toks) if t[0] == "id" and not (i + 1 < len(toks) and toks[i + 1] == ("op", "("))}


def check_syntax(expr):
    """Parses the whole expression without evaluating it. Raises ValueError on any syntax or arity error."""
    toks = tokenize(expr)
    pos = 0

    def peek():
        return toks[pos] if pos < len(toks) else (None, None)

    def take(kind=None, val=None):
        nonlocal pos
        t = peek()
        if t == (None, None) or (kind and t[0] != kind) or (val and t[1] != val):
            raise ValueError(f"parse error at token {pos + 1}")
        pos += 1
        return t

    def factor():
        t = peek()
        if t == ("op", "("):
            take(); add(); take("op", ")")
        elif t == ("op", "-"):
            take(); factor()
        elif t[0] == "num":
            take()
        elif t[0] == "id":
            take()
            if peek() == ("op", "("):
                if t[1] not in FUNCS:
                    raise ValueError(f"unknown function {t[1]}")
                take(); n = 1; add()
                while peek() == ("op", ","):
                    take(); add(); n += 1
                take("op", ")")
                if n != FUNCS[t[1]]:
                    raise ValueError(f"{t[1]} takes {FUNCS[t[1]]} arguments, got {n}")
        else:
            raise ValueError(f"parse error at token {pos + 1}")

    def term():
        factor()
        while peek() in (("op", "*"), ("op", "/")):
            take(); factor()

    def add():
        term()
        while peek() in (("op", "+"), ("op", "-")):
            take(); term()

    add()
    if pos != len(toks):
        raise ValueError("unexpected trailing tokens")


def pmt(rate_pct, years, principal):
    r = rate_pct / 1200.0
    n = years * 12
    if n <= 0:
        raise Null()
    if r == 0:
        return principal / n
    g = (1 + r) ** n
    return principal * r * g / (g - 1)


def evaluate(expr, scope, known_ids):
    toks = tokenize(expr)
    pos = 0

    def peek():
        return toks[pos] if pos < len(toks) else (None, None)

    def take(kind=None, val=None):
        nonlocal pos
        t = peek()
        if (kind and t[0] != kind) or (val and t[1] != val):
            raise ValueError(f"parse error at token {pos + 1}")
        pos += 1
        return t

    def primary():
        t = peek()
        if t == ("op", "("):
            take()
            v = add()
            take("op", ")")
            return v
        if t == ("op", "-"):
            take()
            return -primary()
        if t[0] == "num":
            take()
            return t[1]
        if t[0] == "id":
            take()
            name = t[1]
            if peek() == ("op", "("):
                if name not in FUNCS:
                    raise ValueError(f"unknown function {name}")
                take()
                args = [add()]
                while peek() == ("op", ","):
                    take()
                    args.append(add())
                take("op", ")")
                if len(args) != FUNCS[name]:
                    raise ValueError(f"{name} takes {FUNCS[name]} arguments")
                if name == "pmt":
                    return pmt(*args)
                return min(args) if name == "min" else max(args)
            if name not in known_ids:
                raise ValueError(f"unknown identifier {name}")
            v = scope.get(name)
            if v is None:
                raise Null()
            return float(v)
        raise ValueError("parse error")

    def mul():
        v = primary()
        while peek() in (("op", "*"), ("op", "/")):
            op = take()[1]
            rhs = primary()
            if op == "*":
                v = v * rhs
            else:
                if rhs == 0:
                    raise Null()
                v = v / rhs
        return v

    def add():
        v = mul()
        while peek() in (("op", "+"), ("op", "-")):
            op = take()[1]
            rhs = mul()
            v = v + rhs if op == "+" else v - rhs
        return v

    try:
        v = add()
        if pos != len(toks):
            raise ValueError("unexpected trailing tokens")
        return v
    except Null:
        return None


# ---------- frame ----------

def validate_frame(frame):
    errs = []
    opts = [o["id"] for o in frame["options"]]
    if not 2 <= len(opts) <= 5:
        errs.append(f"{len(opts)} options; need 2 to 5")
    if len(set(opts)) != len(opts):
        errs.append("duplicate option id")
    crit = frame["criteria"]
    if not 3 <= len(crit) <= 7:
        errs.append(f"{len(crit)} criteria; need 3 to 7")
    if len({c['id'] for c in crit}) != len(crit):
        errs.append("duplicate criterion id")
    if not all(isinstance(c["weight"], int) and not isinstance(c["weight"], bool) and c["weight"] >= 0 for c in crit):
        errs.append("weights must be non-negative integers")
    w = sum(c["weight"] for c in crit)
    if w != 100:
        errs.append(f"criteria weights sum to {w}, not 100")
    inputs = frame["inputs"]
    input_ids = [i["id"] for i in inputs]
    metric_ids = [m["id"] for m in frame["metrics"]]
    if len(set(input_ids + metric_ids)) != len(input_ids) + len(metric_ids):
        errs.append("duplicate input or metric id")
    numeric = {i["id"] for i in inputs if i["type"] == "number"}
    non_numeric = {i["id"] for i in inputs if i["type"] != "number"}
    seen = set(numeric)
    for m in frame["metrics"]:
        try:
            check_syntax(m["expr"])
            used = identifiers(m["expr"])
            bad = used & non_numeric
            if bad:
                errs.append(f"metric {m['id']} uses non-numeric input {', '.join(sorted(bad))}")
            unknown = used - seen - non_numeric
            if unknown:
                errs.append(f"metric {m['id']}: unknown identifier {', '.join(sorted(unknown))}")
        except ValueError as e:
            errs.append(f"metric {m['id']}: {e}")
        seen.add(m["id"])
    gate_ids = [g["id"] for g in frame["gates"]]
    if len(set(gate_ids)) != len(gate_ids):
        errs.append("duplicate gate id")
    for g in frame["gates"]:
        if not g["id"].startswith("g_"):
            errs.append(f"gate {g['id']}: id must start with g_")
        if g["subject"] not in seen:
            errs.append(f"gate {g['id']}: subject {g['subject']} is not a numeric input or metric")
        if g["op"] not in OPS:
            errs.append(f"gate {g['id']}: op {g['op']} not allowed")
        if isinstance(g["threshold"], bool) or not isinstance(g["threshold"], (int, float)):
            errs.append(f"gate {g['id']}: threshold must be a number")
        for d in g["depends_on"]:
            if d not in input_ids:
                errs.append(f"gate {g['id']}: depends_on unknown input {d}")
    return errs


def split_proposal(prop):
    """Additive parts apply at once; weight changes and protective gates wait for the user."""
    auto = {"add_inputs": prop["add_inputs"], "add_metrics": prop["add_metrics"],
            "add_gates": [g for g in prop["add_gates"] if not g["protective"]], "change_weights": []}
    held_gates = [g for g in prop["add_gates"] if g["protective"]]
    held = None
    if held_gates or prop["change_weights"]:
        held = {"reason": prop["reason"], "add_inputs": [], "add_metrics": [], "add_gates": held_gates,
                "change_weights": prop["change_weights"]}
    has_auto = bool(auto["add_inputs"] or auto["add_metrics"] or auto["add_gates"])
    return (auto if has_auto else None), held


def apply_proposal(frame, proposal):
    f = copy.deepcopy(frame)
    f["inputs"] += copy.deepcopy(proposal["add_inputs"])
    f["metrics"] += copy.deepcopy(proposal["add_metrics"])
    f["gates"] += copy.deepcopy(proposal["add_gates"])
    weights = {c["criterion_id"]: c["weight"] for c in proposal["change_weights"]}
    for c in f["criteria"]:
        if c["id"] in weights:
            c["weight"] = weights[c["id"]]
    return f


def apply_edit(frame, ch):
    f = copy.deepcopy(frame)

    def find(lst, key, val):
        for x in lst:
            if x[key] == val:
                return x
        raise ValueError(f"frame_edit refers to unknown id {val}")

    for w in ch.get("weights", []):
        find(f["criteria"], "id", w["criterion_id"])["weight"] = w["weight"]
    for t in ch.get("thresholds", []):
        find(f["gates"], "id", t["gate_id"])["threshold"] = t["threshold"]
    for p in ch.get("protective", []):
        find(f["gates"], "id", p["gate_id"])["protective"] = p["protective"]
    for r in ch.get("required", []):
        find(f["inputs"], "id", r["input_id"])["required"] = r["required"]
    for u in ch.get("units", []):
        find(f["inputs"], "id", u["input_id"])["unit"] = u["unit"]
    lists = {"option": "options", "criterion": "criteria", "input": "inputs", "metric": "metrics", "gate": "gates"}
    for lb in ch.get("labels", []):
        find(f[lists[lb["kind"]]], "id", lb["id"])["label"] = lb["label"]
    return f


# ---------- engine ----------

def compare(v, op, t):
    return {"<=": v <= t, ">=": v >= t, "<": v < t, ">": v > t, "==": v == t}[op]


def known(inputs_state, iid):
    s = inputs_state.get(iid)
    return s is not None and s["value"] is not None


def compute(frame, inputs_state, record, prev, v, at, predictions, new_gate_ids, cause="decision", base_v=None):
    numeric = {i["id"] for i in frame["inputs"] if i["type"] == "number"}
    scope = {k: inputs_state[k]["value"] if known(inputs_state, k) else None for k in numeric}
    known_ids = set(numeric)
    metrics = {}
    for m in frame["metrics"]:
        val = round_to(evaluate(m["expr"], scope, known_ids), 4)
        metrics[m["id"]] = val
        scope[m["id"]] = val
        known_ids.add(m["id"])

    gates = []
    for g in frame["gates"]:
        val = scope.get(g["subject"])
        if val is None:
            status = "partial" if any(known(inputs_state, d) for d in g["depends_on"]) else "unknown"
        else:
            status = "pass" if compare(val, g["op"], g["threshold"]) else "fail"
        gates.append({"id": g["id"], "label": g["label"], "subject": g["subject"], "op": g["op"],
                      "threshold": g["threshold"], "threshold_text": g["threshold_text"],
                      "protective": g["protective"], "value": val, "status": status,
                      "is_new": g["id"] in new_gate_ids})

    required = [i for i in frame["inputs"] if i["required"]]
    weight, count = 0.0, 0
    for i in required:
        s = inputs_state.get(i["id"])
        if known(inputs_state, i["id"]) and s["source"] != "assumed":
            count += 1
            weight += SOURCE_WEIGHT[s["source"]]
    evidence = {"known": count, "required": len(required),
                "strength": round_to(weight / len(required), 2) if required else 0}

    opt_ids = [o["id"] for o in frame["options"]]
    rows, totals = [], {o: 0.0 for o in opt_ids}
    by_crit = {r["criterion_id"]: r for r in record["matrix"]}
    for c in frame["criteria"]:
        r = by_crit[c["id"]]
        sc = {s["option_id"]: {"score": s["score"], "assumed": s["assumed"]} for s in r["scores"]}
        for o in opt_ids:
            totals[o] += c["weight"] * sc[o]["score"]
        rows.append({"criterion_id": c["id"], "label": c["label"], "weight": c["weight"], "scores": sc, "basis": r["basis"]})
    totals = {o: round_to(t / 5, 0) for o, t in totals.items()}

    risk = record["scores"]["risk"]
    protective = [g for g in gates if g["protective"]]
    if record["coherence"]["level"] == "low":
        ceiling = "observe"
    elif protective and all(g["status"] == "pass" for g in protective) and risk <= 50 \
            and record["reality"]["executable_under_constraints"]:
        ceiling = "prepare"
    elif count >= 3:
        ceiling = "simulate"
    else:
        ceiling = "recommend"
    ci = LADDER.index(ceiling)
    bounds = [{"level": b["level"], "action": b["action"],
               "status": "needs_user" if b["level"] == "request_warrant" else ("within" if LADDER.index(b["level"]) <= ci else "above")}
              for b in record["action_bounds"]]

    if prev is None:
        belief = {"text": record["claim"], "since_v": v, "history": []}
    elif prev["belief"]["text"] == record["claim"]:
        belief = copy.deepcopy(prev["belief"])
    else:
        pb = prev["belief"]
        belief = {"text": record["claim"], "since_v": v, "history": pb["history"] + [{"v": pb["since_v"], "text": pb["text"]}]}

    state = {
        "format": "settle-state", "version": 1,
        "v": v, "cause": cause, "base_v": base_v,
        "superseded": list(prev["superseded"]) if prev else [],
        "frame_version": frame["frame_version"], "updated_at": at,
        "status": record["status"], "verdict": record["verdict"], "summary": record["summary"],
        "direction": record["direction"], "belief": belief,
        "inputs": copy.deepcopy(inputs_state), "metrics": metrics,
        "scores": {"confidence": record["scores"]["confidence"], "risk": risk},
        "risk": record["risk"],
        "matrix": rows, "totals": totals, "gates": gates, "evidence": evidence,
        "assumptions": record["falsifiability"]["assumptions"],
        "predictions": copy.deepcopy(predictions), "calibration": calibration(predictions),
        "ceiling": ceiling, "action_bounds": bounds,
        "coherence": record["coherence"],
    }
    set_deltas(state, prev)
    return state


def set_deltas(state, prev):
    """System confidence and deltas against the previous version. Used by every kind that creates a version."""
    if prev is None:
        state["system_confidence"] = "evolving"
        state["deltas"] = None
        return
    conf = state["scores"]["confidence"]
    state["system_confidence"] = "stable" if abs(conf - prev["scores"]["confidence"]) < 15 else "evolving"
    prev_scores = {r["criterion_id"]: r["scores"] for r in prev["matrix"]}
    prev_gates = {g["id"]: g["status"] for g in prev["gates"]}
    opts = list(state["totals"])
    state["deltas"] = {
        "confidence": conf - prev["scores"]["confidence"],
        "risk": state["scores"]["risk"] - prev["scores"]["risk"],
        "evidence_strength": round_to(state["evidence"]["strength"] - prev["evidence"]["strength"], 2),
        "totals": {o: state["totals"][o] - prev["totals"].get(o, 0) for o in opts},
        "gates_passed": sum(g["status"] == "pass" for g in state["gates"]) - sum(g["status"] == "pass" for g in prev["gates"]),
        "ceiling_steps": LADDER.index(state["ceiling"]) - LADDER.index(prev["ceiling"]),
        "criteria_changed": [r["criterion_id"] for r in state["matrix"]
                             if any(r["scores"][o]["score"] != prev_scores.get(r["criterion_id"], {}).get(o, {}).get("score") for o in opts)],
        "gates_changed": [g["id"] for g in state["gates"] if prev_gates.get(g["id"]) != g["status"]],
    }


def calibration(predictions):
    held = sum(p["status"] == "held" for p in predictions)
    missed = sum(p["status"] == "missed" for p in predictions)
    return {"resolved": held + missed, "held": held, "missed": missed, "graded_by": "user" if held + missed else "none"}


def invariants(frame, record, held=None):
    """Checks that reject a turn. `frame` is the frame after any auto-applied proposal parts."""
    out = []
    w = sum(c["weight"] for c in frame["criteria"])
    out.append({"id": "weights_sum_100", "ok": w == 100, "detail": f"weights sum to {w}"})
    opt = [o["id"] for o in frame["options"]]
    rng = all(isinstance(s["score"], int) and not isinstance(s["score"], bool) and 1 <= s["score"] <= 5
              for r in record["matrix"] for s in r["scores"])
    out.append({"id": "scores_in_range", "ok": rng, "detail": "every score is an integer from 1 to 5"})
    crits = sorted(r["criterion_id"] for r in record["matrix"])
    complete = crits == sorted(c["id"] for c in frame["criteria"]) and all(
        sorted(s["option_id"] for s in r["scores"]) == sorted(opt) for r in record["matrix"])
    out.append({"id": "matrix_complete", "ok": complete, "detail": "every criterion scored once for every option"})
    types = {i["id"]: i["type"] for i in frame["inputs"]}
    unknown = [i["id"] for i in record["inputs"] if i["id"] not in types]
    out.append({"id": "inputs_in_frame", "ok": not unknown,
                "detail": ("unknown inputs: " + ", ".join(unknown)) if unknown else "all inputs are defined in the frame"})

    def type_ok(i):
        v, t = i["value"], types.get(i["id"])
        if v is None or t is None:
            return True
        if t == "number":
            return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
        if t == "boolean":
            return isinstance(v, bool)
        return isinstance(v, str)
    bad_types = [i["id"] for i in record["inputs"] if not type_ok(i)]
    out.append({"id": "input_types_match", "ok": not bad_types,
                "detail": ("wrong value type for: " + ", ".join(bad_types)) if bad_types else "every input value matches its type"})
    bad_opt = [b["option_id"] for b in record["falsifiability"]["break_conditions"]
               if (b["option_id"] is not None and b["option_id"] not in opt)
               or (b["effect"] in ("favours_option", "flips_decision") and b["option_id"] is None)]
    out.append({"id": "option_refs_valid", "ok": not bad_opt, "detail": "break conditions reference real options where needed"})
    pct = all(isinstance(record["scores"][k], int) and not isinstance(record["scores"][k], bool)
              and 0 <= record["scores"][k] <= 100 for k in ("confidence", "risk"))
    out.append({"id": "scores_0_100", "ok": pct, "detail": "confidence and risk are integers from 0 to 100"})
    cut = [k for k in ("reply", "claim", "summary", "direction") if not record[k].rstrip().endswith(TERMINAL)]
    out.append({"id": "no_truncated_text", "ok": not cut,
                "detail": ("cut fields: " + ", ".join(cut)) if cut else "reply, claim, summary and direction end cleanly"})
    frame_errs = validate_frame(frame)
    out.append({"id": "frame_valid", "ok": not frame_errs, "detail": "; ".join(frame_errs) or "frame is valid"})
    held_errs = validate_frame(apply_proposal(frame, held)) if held else []
    out.append({"id": "proposal_valid", "ok": not held_errs,
                "detail": ("; ".join(held_errs)) if held_errs else "any pending proposal would leave a valid frame"})
    return out


# ---------- reducer over the log ----------

def run(conv):
    """Replays a decision log. Entry kinds:
    decision       applied turn with model output         -> new version
    frame_accept   user accepts the pending proposal       -> new version (recomputed from the last record)
    frame_dismiss  user dismisses the pending proposal     -> same version; pending proposal cleared
    frame_edit     user edits weights, thresholds, protective flags, required flags, units, labels -> new version
    rewind         user restores version to_v             -> new version equal to to_v, base_v = to_v
    grade          user grades a prediction               -> same version; predictions and calibration change
    meta, clarify, failed                                 -> logged only; state unchanged
    """
    log, states, by_v = [], [], {}
    prev_hash = "genesis"
    frame, inputs_state, state = None, {}, None
    predictions, pending, last_record = [], None, None
    v, max_fv = 0, 0

    def new_frame_version(f):
        nonlocal max_fv
        max_fv += 1
        f["frame_version"] = max_fv
        return f

    def finish(new_state, entry, inv):
        new_state.update({"decision_id": conv["decision_id"], "title": frame["title"], "frame": copy.deepcopy(frame),
                          "pending_frame_proposal": copy.deepcopy(pending), "invariants": inv, "log_head": entry["hash"]})
        by_v[new_state["v"]] = (copy.deepcopy(frame), copy.deepcopy(inputs_state), copy.deepcopy(last_record), copy.deepcopy(new_state))
        states.append(copy.deepcopy(new_state))
        return new_state

    def reject(failed):
        raise AssertionError(f"rejected by invariants: {[f['id'] + ': ' + f['detail'] for f in failed]}")

    for seq, ev in enumerate(conv["events"], start=1):
        entry = dict(ev)
        entry.update({"seq": seq, "decision_id": conv["decision_id"], "prev_hash": prev_hash})
        entry["hash"] = sha256(entry)
        prev_hash = entry["hash"]
        log.append(entry)
        kind = ev["kind"]

        if kind == "decision":
            assert ev["route"]["route"] in APPLIED_ROUTES, "decision entries need an applied route"
            rec = ev["output"]["record"]
            new_gate_ids = set()
            if frame is None:
                assert "frame" in ev["output"], "the first decision entry must carry a frame"
                frame = new_frame_version(copy.deepcopy(ev["output"]["frame"]))
                inputs_state = {i["id"]: None for i in frame["inputs"]}
            candidate, held = frame, pending
            if rec["frame_proposal"]:
                auto, new_held = split_proposal(rec["frame_proposal"])
                if new_held is not None:
                    held = new_held
                if auto:
                    candidate = apply_proposal(frame, auto)
                    new_gate_ids = {g["id"] for g in auto["add_gates"]}
            inv = invariants(candidate, rec, held)
            failed = [i for i in inv if not i["ok"]]
            if failed:
                reject(failed)
            if candidate is not frame:
                frame = new_frame_version(candidate)
                for i in auto["add_inputs"]:
                    inputs_state.setdefault(i["id"], None)
            pending = held  # a new held part replaces the old one; with no new held part the old one stays (held == pending)
            v += 1
            for i in rec["inputs"]:
                old = inputs_state.get(i["id"])
                since = old["since_v"] if old and old["value"] == i["value"] else v
                inputs_state[i["id"]] = {"value": i["value"], "source": i["source"], "note": i["note"], "since_v": since}
            predictions = predictions + [{"id": f"p{v}", "made_in": v, "text": rec["prediction"]["text"],
                                          "check_at": utc_iso(ev["at"], rec["prediction"]["check_after_hours"]), "status": "open"}]
            last_record = rec
            state = finish(compute(frame, inputs_state, rec, state, v, ev["at"], predictions, new_gate_ids), entry, inv)

        elif kind in ("frame_accept", "frame_edit"):
            assert state is not None, f"{kind} before the first decision"
            new_gate_ids = set()
            if kind == "frame_accept":
                assert pending, "frame_accept without a pending proposal"
                candidate = apply_proposal(frame, pending)
                new_gate_ids = {g["id"] for g in pending["add_gates"]}
            else:
                assert pending is None, "frame_edit while a proposal is pending: accept or dismiss it first"
                candidate = apply_edit(frame, ev["changes"])
            inv = invariants(candidate, last_record)
            failed = [i for i in inv if not i["ok"]]
            if failed:
                reject(failed)
            frame = new_frame_version(candidate)
            if kind == "frame_accept":
                pending = None
            v += 1
            state = finish(compute(frame, inputs_state, last_record, state, v, ev["at"], predictions, new_gate_ids, cause=kind), entry, inv)

        elif kind == "frame_dismiss":
            assert state is not None and pending, "frame_dismiss without a pending proposal"
            pending = None
            state = dict(state, pending_frame_proposal=None, log_head=entry["hash"])

        elif kind == "rewind":
            to_v = ev["to_v"]
            assert to_v in by_v and to_v < v, "rewind target must be an earlier version"
            assert to_v not in state["superseded"], "cannot rewind to a superseded version"
            frame, inputs_state, last_record, old = copy.deepcopy(by_v[to_v])
            pending = old["pending_frame_proposal"]
            prev = state
            v += 1
            restored = copy.deepcopy(old)
            restored.update({"v": v, "cause": "rewind", "base_v": to_v, "updated_at": ev["at"],
                             "superseded": sorted(set(prev["superseded"]) | set(range(to_v + 1, v))),
                             "predictions": copy.deepcopy(predictions), "calibration": calibration(predictions),
                             "log_head": entry["hash"]})
            for g in restored["gates"]:
                g["is_new"] = False
            set_deltas(restored, prev)
            by_v[v] = (copy.deepcopy(frame), copy.deepcopy(inputs_state), copy.deepcopy(last_record), copy.deepcopy(restored))
            state = restored
            states.append(copy.deepcopy(state))

        elif kind == "grade":
            assert state is not None and any(p["id"] == ev["prediction_id"] for p in predictions), "unknown prediction"
            assert ev["status"] in ("held", "missed", "open")
            predictions = [dict(p, status=ev["status"]) if p["id"] == ev["prediction_id"] else p for p in predictions]
            state = dict(state, predictions=copy.deepcopy(predictions), calibration=calibration(predictions), log_head=entry["hash"])

        elif kind in ("meta", "clarify", "failed"):
            assert state is not None, f"{kind} before the first decision: nothing is logged until a decision exists"
            if kind == "meta":
                assert ev["route"]["route"] == "meta", "meta entries carry the meta route"
            if kind == "clarify":
                assert ev["route"]["route"] not in APPLIED_ROUTES or ev.get("user_choice") == "comment", \
                    "clarify entries carry an applied route only when the user chose 'just a comment'"
            state = dict(state, log_head=entry["hash"])
        else:
            raise ValueError(f"unknown entry kind {kind}")
    return log, states, state


def summary(states, final):
    return {
        "versions": [{
            "v": s["v"], "cause": s["cause"], "base_v": s["base_v"], "frame_version": s["frame_version"],
            "totals": s["totals"], "confidence": s["scores"]["confidence"], "risk": s["scores"]["risk"],
            "evidence": s["evidence"], "ceiling": s["ceiling"], "system_confidence": s["system_confidence"],
            "gates": {g["id"]: [g["status"], g["value"]] for g in s["gates"]},
            "metrics": s["metrics"], "deltas": s["deltas"], "superseded": s["superseded"],
            "pending_frame_proposal": s["pending_frame_proposal"] is not None,
        } for s in states],
        "final": {"v": final["v"], "calibration": final["calibration"], "log_head": final["log_head"],
                  "pending_frame_proposal": final["pending_frame_proposal"] is not None},
    }


def write_vectors(path):
    cases = [
        {"name": "zero", "value": 0}, {"name": "negative zero", "value": -0.0},
        {"name": "integer float", "value": 8.0}, {"name": "decimal", "value": 8.5},
        {"name": "binary fraction", "value": 0.1 + 0.2}, {"name": "metric", "value": 76368.4445},
        {"name": "small", "value": 0.000001}, {"name": "smaller", "value": 1e-7},
        {"name": "large", "value": 123456789012345680000.0}, {"name": "very large", "value": 1e21},
        {"name": "2^53", "value": 9007199254740992}, {"name": "2^53 + 2 (float)", "value": 9007199254740994.0},
        {"name": "2^60 (float)", "value": float(2 ** 60)},
        {"name": "negative exponent", "value": -1.5e-10},
        {"name": "money", "value": 11000000}, {"name": "ratio", "value": 0.2288},
        {"name": "unicode string", "value": "₹1.1 Cr · ‘quoted’ — dash"},
        {"name": "control characters", "value": "line\nbreak\ttab\u0001"},
        {"name": "key order (UTF-16 code units)", "value": {"ｚ": 4, "😀": 3, "é": 2, "a": 1, "B": 0}},
        {"name": "nested", "value": {"b": [1, {"d": True, "c": None}], "a": "x"}},
    ]
    for c in cases:
        c["canonical"] = canonical(c["value"])
        c["sha256"] = hashlib.sha256(c["canonical"].encode("utf-8")).hexdigest()
    doc = {"note": "Canonical JSON test vectors (RFC 8785). In TS: expect(canonical(value)).toBe(c.canonical) and sha256Hex(...) toBe(c.sha256). -0.0 and 8.0 are written in this file as JSON numbers, which TS parses as -0 and 8.",
           "cases": cases}
    Path(path).write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(cases)} vectors to {path}")


def selftest():
    """Error cases for the expression parser, frame validation and invariants. Mirror these as unit tests in TS."""
    ok = 0
    for expr, msg in [("(a + b", "parse error"), ("pmt(a, b)", "takes 3 arguments"), ("a a", "trailing"),
                      ("a $ b", "unexpected character"), ("foo(a)", "unknown function"), ("", "parse error")]:
        try:
            check_syntax(expr)
            raise AssertionError(f"accepted bad expression {expr!r}")
        except ValueError as e:
            assert msg in str(e), (expr, str(e))
            ok += 1
    for expr in ["pmt(r, y, p) + 1", "-(a - b) / c * 2", "min(a, max(b, 3.5))"]:
        check_syntax(expr)
        ok += 1
    assert round_to(76368.44445, 4) == 76368.4445 and round_to(-2.5, 0) == -3 and round_to(2.5, 0) == 3
    assert evaluate("a / (b - b)", {"a": 1, "b": 2}, {"a", "b"}) is None, "division by zero is null"
    assert evaluate("a + b", {"a": 1, "b": None}, {"a", "b"}) is None, "null propagates"
    assert round_to(evaluate("pmt(8.5, 20, 8800000)", {}, set()), 4) == 76368.4445
    ok += 6
    conv = json.loads((Path(__file__).resolve().parent.parent / "fixtures/rent-or-buy/conversation.json").read_text(encoding="utf-8"))
    base = copy.deepcopy(conv["events"][0]["output"]["frame"])
    cases = {
        "weights sum": lambda f: f["criteria"][0].update(weight=30),
        "need 2 to 5": lambda f: f.update(options=f["options"][:1]),
        "must start with g_": lambda f: f["gates"][0].update(id="stay"),
        "non-numeric input": lambda f: f["metrics"].append({"id": "x", "label": "x", "unit": "", "expr": "down_payment_covered * 2"}),
        "is not a numeric input or metric": lambda f: f["gates"][0].update(subject="down_payment_covered"),
        "takes 3 arguments": lambda f: f["metrics"][1].update(expr="pmt(loan_rate_pct, loan_principal)"),
        "unknown identifier": lambda f: f["metrics"][0].update(expr="purchase_price * later_metric"),
        "duplicate gate id": lambda f: f["gates"].append(copy.deepcopy(f["gates"][0])),
    }
    for msg, mutate in cases.items():
        f = copy.deepcopy(base)
        mutate(f)
        errs = validate_frame(f)
        assert any(msg in e for e in errs), (msg, errs)
        ok += 1
    assert validate_frame(base) == []
    rec = copy.deepcopy(conv["events"][3]["output"]["record"])
    frame = copy.deepcopy(base)
    rec["inputs"][1]["value"] = "₹42,000"
    held = {"reason": "", "add_inputs": [], "add_metrics": [], "add_gates": [], "change_weights": [{"criterion_id": "flexibility", "weight": 30}]}
    inv = {i["id"]: i["ok"] for i in invariants(frame, rec, held)}
    assert inv["input_types_match"] is False and inv["proposal_valid"] is False, inv
    ok += 2
    print(f"selftest OK ({ok} checks)")
    return 0


def main(argv):
    if argv and argv[0] == "--vectors":
        write_vectors(argv[1])
        return 0
    if argv and argv[0] == "--selftest":
        return selftest()
    check = "--check" in argv
    args = [a for a in argv if a != "--check"]
    conv = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    outdir = Path(args[1])
    log, states, final = run(conv)
    files = {"log.json": log, "final-state.json": final, "summary.json": summary(states, final)}
    for s in states:
        files[f"state-v{s['v']}.json"] = s
    mismatches = []
    for name, data in files.items():
        text = json.dumps(normalize(data), indent=2, ensure_ascii=False, sort_keys=True) + "\n"
        path = outdir / name
        if check:
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                mismatches.append(name)
        else:
            outdir.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
    if check:
        extra = sorted(p.name for p in outdir.glob("*.json") if p.name not in files) if outdir.exists() else []
        if mismatches or extra:
            print("MISMATCH:", ", ".join(mismatches + [f"unexpected {e}" for e in extra]))
            return 1
        print("OK: expected files match")
        return 0
    for stale in outdir.glob("state-v*.json"):
        if stale.name not in files:
            stale.unlink()
    print(f"Wrote {len(files)} files to {outdir}")
    for s in states:
        print(f"v{s['v']} ({s['cause']}): totals {s['totals']} ceiling {s['ceiling']} evidence {s['evidence']['known']}/{s['evidence']['required']} "
              f"fv {s['frame_version']} pending {s['pending_frame_proposal'] is not None} superseded {s['superseded']} gates "
              + ", ".join(f"{g['id']}={g['status']}" for g in s["gates"]))
    print("final log head:", final["log_head"][:12], "calibration:", final["calibration"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
