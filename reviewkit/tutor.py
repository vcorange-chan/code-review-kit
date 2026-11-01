"""Mechanical teaching operations shared by CLI and skills; no model calls."""

from contextlib import contextmanager
import copy
import json
from pathlib import Path

from .lecture import check_lecture, fact_nodes, segments
from .source_identity import verify_source
from .storage import digest, read_json, write_json


def find_step(lecture, step_id, planned=False):
    choices = [*lecture["steps"], *(lecture.get("outline", []) if planned else [])]
    step = next((s for s in choices if s["id"] == step_id), None)
    if step is None:
        raise ValueError("Unknown lecture step: " + step_id)
    return step


def check_source_lock(lecture, facts):
    identity = verify_source(facts)
    if lecture.get("source_identity") and lecture["source_identity"] != identity:
        raise ValueError("Lecture source identity differs; use its original facts snapshot")
    return identity


def auto_gaps(lecture, step, node, deferred=(), remainder=None):
    """Compute range complements; teaching destinations come from the author/outline."""
    first, last = node["line"], node["end_line"]
    shown = set()
    for a, b in step["show"]:
        if not first <= a <= b <= last:
            raise ValueError("Invalid visible source range")
        if shown.intersection(range(a, b + 1)):
            raise ValueError("Overlapping visible source ranges")
        shown.update(range(a, b + 1))
    assigned = {}
    for gap in deferred:
        a, b = gap["lines"]
        if not first <= a <= b <= last or not gap.get("label"):
            raise ValueError("Deferred range needs valid lines and a label")
        for n in range(a, b + 1):
            if n in shown or n in assigned:
                raise ValueError("Deferred range overlaps another selection")
            assigned[n] = {k: v for k, v in gap.items() if k != "lines"}
    gaps = []
    for n in range(first, last + 1):
        if n in shown:
            continue
        destination = assigned.get(n)
        if destination is None:
            other = next((s for s in [*lecture["steps"], *lecture.get("outline", [])] if s["id"] != step["id"] and s["node"] == step["node"]
                          and any(a <= n <= b for a, b in s.get("show", []))), None)
            destination = ({"label": other.get("short", other["id"]), "ref": other["id"]} if other
                           else dict(remainder or {"label": "本步未展开 · 去向待安排"}))
        if gaps and gaps[-1]["lines"][1] == n - 1 and {k: v for k, v in gaps[-1].items() if k != "lines"} == destination:
            gaps[-1]["lines"][1] = n
        else:
            gaps.append({"lines": [n, n], **destination})
    return gaps


def prepare_step(lecture, facts, step):
    nodes = fact_nodes(facts)
    if step["node"] not in nodes:
        raise ValueError("Missing facts node: " + step["node"])
    node = nodes[step["node"]]
    result = copy.deepcopy(step)
    result.setdefault("show", [])
    if "gaps" not in result:
        result["gaps"] = auto_gaps(lecture, result, node, result.get("defer", []), result.get("remainder"))
    stubs = []
    for stub in result.get("stubs", []):
        if "node" not in stub:
            stubs.append({**stub, "unverified_signature": True})
            continue
        target = nodes.get(stub["node"])
        if not target or not target.get("signature"):
            raise ValueError("Signature requires an extracted function: " + stub["node"])
        stubs.append({"node": stub["node"], "name": target["signature"],
                      "where": f'{target["file"]} L{target["line"]}', "ref": stub.get("ref", ""),
                      "evidence_hash": target["hash"]})
    result["stubs"] = stubs
    segments(result, node["line"], node["end_line"])
    return result


@contextmanager
def locked_json(path, initial=None):
    """Serialize tool updates; a crashed process leaves a visible lock, never guessed away."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name + ".lock")
    try:
        handle = lock.open("x", encoding="utf-8")
    except FileExistsError:
        raise ValueError("Another update holds the file lock: " + path.name) from None
    try:
        handle.close()
        yield read_json(path) if path.is_file() else copy.deepcopy(initial)
    finally:
        lock.unlink()


def retell(path, facts, step_id, replacement, expected_revision, reason=""):
    protected = {"id", "node", "r", "earlier", "evidence_hash", "source_identity"}
    if protected.intersection(replacement):
        raise ValueError("Retelling cannot replace identity/history fields")
    with locked_json(path) as lecture:
        check_lecture(lecture)
        identity = check_source_lock(lecture, facts)
        step = find_step(lecture, step_id)
        if step.get("r", 1) != expected_revision:
            raise ValueError("Outdated retell request; read the current revision first")
        node = fact_nodes(facts)[step["node"]]
        if step.get("evidence_hash") != node["hash"]:
            raise ValueError("Review stale source evidence before retelling")
        old = copy.deepcopy({k: v for k, v in step.items() if k != "earlier"})
        old.update({"r": expected_revision, "reason": reason, "source_identity": identity})
        old = prepare_step(lecture, facts, old)
        updated = {**step, **copy.deepcopy(replacement), "r": expected_revision + 1,
                   "earlier": [*step.get("earlier", []), old]}
        if "show" in replacement and "gaps" not in replacement:
            updated.pop("gaps", None)
        updated = prepare_step(lecture, facts, updated)
        lecture["steps"][lecture["steps"].index(step)] = updated
        check_lecture(lecture)
        write_json(path, lecture)
        return {"step": step_id, "r": updated["r"], "archived_revision": expected_revision}


def append_step(path, facts, step_id, draft):
    """Add one authored step without asking the model to rewrite the whole notebook."""
    with locked_json(path) as lecture:
        check_lecture(lecture)
        identity = check_source_lock(lecture, facts)
        if any(s["id"] == step_id for s in lecture["steps"]):
            raise ValueError("Step already exists; use retell instead")
        planned = next((s for s in lecture.get("outline", []) if s["id"] == step_id), {})
        new = {**planned, **copy.deepcopy(draft), "id": step_id, "r": 1}
        if draft.get("id", step_id) != step_id or draft.get("earlier") or draft.get("r", 1) != 1:
            raise ValueError("A new step cannot replace identity/history")
        if planned and planned["node"] != new["node"]:
            raise ValueError("Step node differs from the confirmed outline")
        node = fact_nodes(facts)[new["node"]]
        if new.get("evidence_hash", node["hash"]) != node["hash"]:
            raise ValueError("New step evidence differs from its facts")
        if identity and not lecture.get("source_identity"):
            if lecture["steps"]:
                raise ValueError("Lock the existing lecture source before adding steps")
            lecture["source_identity"] = identity
        new["evidence_hash"] = node["hash"]
        lecture["steps"].append(prepare_step(lecture, facts, new))
        check_lecture(lecture)
        write_json(path, lecture)
        return {"step": step_id, "r": 1, "steps": len(lecture["steps"])}


def step_packet(lecture, facts, step_id, budget=12000, records=(), explanations=None, revision=None):
    if budget < 2048:
        raise ValueError("Step packet budget must be at least 2048 UTF-8 bytes")
    identity = check_source_lock(lecture, facts)
    step = find_step(lecture, step_id, planned=True)
    current = step.get("r", 1)
    if revision is not None and revision != current:
        step = next((s for s in step.get("earlier", []) if s["r"] == revision), None)
        if step is None:
            raise ValueError("Unknown archived revision")
    step = prepare_step(lecture, facts, step)
    nodes = fact_nodes(facts)
    node = nodes[step["node"]]
    packet = {
        "schema_version": 1, "lecture": lecture["id"], "step": step_id,
        "r": step.get("r", 1), "source_identity": identity,
        "evidence_hash": step.get("evidence_hash"), "current_node_hash": node["hash"],
        "evidence_current": step.get("evidence_hash") == node["hash"],
        "output_language": lecture.get("output_language", "zh"),
        "budget_bytes": budget, "omitted_counts": {}, "packet_hash": "0" * 64,
        "rules": ["Fixed source; reveal lines, never invent patches.",
                  "Review behavior is not evidence of author intent.",
                  "Syntax candidates are not runtime dispatch proof.",
                  "Omitted material remains in the original files."],
    }

    def size():
        return len(json.dumps(packet, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

    def add(key, value):
        items = packet.setdefault(key, [])
        items.append(value)
        if size() > budget - 150:
            items.pop()
            packet["omitted_counts"][key] = packet["omitted_counts"].get(key, 0) + 1

    add("context", {k: lecture[k] for k in ("scenario", "observable", "invariants") if k in lecture})
    add("node", {k: node[k] for k in ("id", "file", "line", "end_line", "signature") if k in node})
    add("teaching", {k: step[k] for k in ("goal", "reasons", "method", "progress", "behavior", "consider", "place") if k in step})
    source = node["source"].split("\n")
    for a, b in step["show"]:
        for n in range(a, b + 1):
            add("code", {"file": node["file"], "line": n, "text": source[n - node["line"]]})
    if not step["show"]:
        for statement in node.get("statements", []):
            add("layout", statement)
    visible = {n for a, b in step["show"] for n in range(a, b + 1)}
    for key in ("branches", "calls", "errors", "returns", "imports"):
        for item in node.get(key, []):
            if not isinstance(item, dict) or "line" not in item or item["line"] in visible or key == "imports":
                add(key, item)
    for stub in step["stubs"]:
        add("signatures", stub)
    called = {candidate for edge in facts.get("edges", []) if edge["from"] == node.get("function_id", node["id"])
              and edge["line"] in visible for candidate in edge["candidates"]}
    for ident in sorted(called):
        if ident in nodes:
            add("call_candidates", {"id": ident, "signature": nodes[ident].get("signature"), "status": "syntax_candidate"})
    for item in facts.get("types", []):
        add("types", {k: item[k] for k in ("name", "file", "line", "text", "hash") if k in item})
    if explanations:
        card = explanations.get("cards", {}).get(step["node"])
        if explanations.get("output_language", "zh") != lecture.get("output_language", "zh"):
            packet["review_behavior_language_mismatch"] = True
        elif card and card.get("evidence_hash", explanations.get("evidence_hash")) == facts.get("card_evidence", {}).get(step["node"]):
            add("review_behavior", {k: card[k] for k in ("input", "steps", "errors", "normal_output") if k in card})
        elif card:
            packet["review_behavior_stale"] = True
    for record in reversed(list(records)):
        if record.get("lecture") == lecture["id"] and record.get("step") == step_id and record.get("r") == step.get("r", 1):
            add("discussion", record)
    for key in reversed([k for k, v in packet.items() if isinstance(v, list) and k != "rules"]):
        while size() > budget and packet[key]:
            packet[key].pop()
            packet["omitted_counts"][key] = packet["omitted_counts"].get(key, 0) + 1
    packet["packet_hash"] = digest({k: v for k, v in packet.items() if k != "packet_hash"})
    if size() > budget:
        raise ValueError("Packet exceeds budget; increase --bytes")
    return packet


def write_packet(path, packet):
    raw = json.dumps(packet, ensure_ascii=False, separators=(",", ":"))
    path = Path(path)
    reused = path.is_file() and path.read_text(encoding="utf-8") == raw
    if not reused:
        write_json(path, packet, compact=True)
    return {"packet": str(path.resolve()), "bytes": len(raw.encode("utf-8")), "reused": reused}


def cursor_status(lecture, state_path):
    state = read_json(state_path) if Path(state_path).is_file() else {}
    if state and (state.get("lecture") != lecture["id"] or state.get("source_identity") != lecture.get("source_identity")):
        raise ValueError("Reading state belongs to another lecture/source snapshot")
    current = state.get("current") or (lecture["steps"][0]["id"] if lecture["steps"] else None)
    step = next((s for s in lecture["steps"] if s["id"] == current), None)
    return {"lecture": lecture["id"], "source_identity": lecture.get("source_identity"), "current": current,
            "revision": step.get("r", 1) if step else None, "needs_authoring": current is not None and step is None,
            "last_request": state.get("last_request"), "end_of_outline": bool(state.get("end_of_outline")), "position_only": True}


def move_cursor(lecture, state_path, action, step_id, expected_revision):
    check_lecture(lecture)
    step = find_step(lecture, step_id)
    if step.get("r", 1) != expected_revision:
        raise ValueError("Outdated navigation request; read the current revision first")
    request = f'{action}:{lecture["id"]}/{step_id}.r{expected_revision}'
    with locked_json(state_path, {}) as state:
        status = cursor_status(lecture, state_path)
        if state.get("last_request") == request:
            return {**status, "reused": True}
        if action == "next" and status["current"] != step_id:
            raise ValueError("Navigation starts at another step; use resume to choose explicitly")
        route = [s["id"] for s in lecture.get("outline", lecture["steps"])]
        if step_id not in route:
            raise ValueError("Current step is missing from the confirmed outline")
        index = route.index(step_id)
        next_step = route[index + 1] if action == "next" and index + 1 < len(route) else step_id
        result = {"schema_version": 1, "lecture": lecture["id"], "source_identity": lecture.get("source_identity"),
                  "current": next_step, "last_request": request, "end_of_outline": action == "next" and index + 1 == len(route)}
        write_json(state_path, result)
    return {**cursor_status(lecture, state_path), "end_of_outline": result["end_of_outline"], "reused": False}
