"""Local append-only investigation ledger. Valid evidence IDs are not reasoning proof."""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from .evidence import ID, verify
from .storage import digest, read_json, write_json

KINDS = {"brief", "plan", "hypothesis", "finding", "unknown", "note", "handoff"}
STATES = {
    "hypothesis": {"open", "testing", "supported", "refuted", "abandoned"},
    "unknown": {"open", "investigating", "blocked", "contradicted", "resolved"},
}


@contextmanager
def locked(session):
    root = Path(session)
    root.mkdir(parents=True, exist_ok=True)
    lock = root / ".write.lock"
    try:
        handle = lock.open("x", encoding="utf-8")
    except FileExistsError as error:
        raise ValueError(
            "Investigation is locked; inspect any interrupted writer before removing the lock"
        ) from error
    try:
        with handle:
            yield root
    finally:
        lock.unlink()


def load_evidence(session, ident):
    if not isinstance(ident, str) or not ID.fullmatch(ident):
        raise ValueError("Invalid evidence ID")
    return verify(read_json(Path(session) / "evidence" / (ident + ".json")))


def import_evidence(session, bundle):
    items = bundle.get("evidence", []) if isinstance(bundle, dict) else bundle
    if not isinstance(items, list) or not items:
        raise ValueError("Expected a nonempty evidence bundle")
    for item in items:
        verify(item)
    with locked(session) as root:
        for item in items:
            path = root / "evidence" / (item["id"] + ".json")
            if path.exists():
                verify(read_json(path))
            else:
                write_json(path, item)
    return {"imported": len(items), "ids": [item["id"] for item in items]}


def read_history(session):
    path = Path(session) / "history.jsonl"
    events = []
    if not path.exists():
        return events
    raw = path.read_text(encoding="utf-8")
    if raw and not raw.endswith("\n"):
        raise ValueError(
            "Incomplete investigation history append; preserve and inspect the file"
        )
    for number, line in enumerate(raw.splitlines(), 1):
        if not line:
            raise ValueError("Blank/incomplete investigation history row")
        event = json.loads(line)
        body = {k: v for k, v in event.items() if k != "hash"}
        if (
            event.get("revision") != number
            or event.get("previous") != (events[-1]["hash"] if events else None)
            or event.get("hash") != digest(body)
        ):
            raise ValueError("Investigation history chain mismatch")
        events.append(event)
    return events


def snapshot(session):
    events = read_history(session)
    latest = {}
    for event in events:
        latest[event["record"]["id"]] = event["record"]
    # Verify references on read as well as append. Missing/tampered evidence refuses export.
    identities = set()
    for event in events:
        for ident in [
            *event["record"].get("support", []),
            *event["record"].get("counter", []),
        ]:
            item = load_evidence(session, ident)
            identity = item["subject"].get("source_identity") or item["subject"].get(
                "scope_id"
            )
            if identity:
                identities.add(identity)
    return {
        "schema_version": 1,
        "revision": len(events),
        "records": list(latest.values()),
        "history": events,
        "source_identities": sorted(identities),
        "mixed_sources": len(identities) > 1,
        "limits": [
            "author_judgments_not_automatically_verified",
            "evidence_reference_validation_not_reasoning_proof",
            "hash_chain_detects_edits_not_authenticated_external_anchoring",
            "not_learner_mastery",
        ],
    }


def append(session, record, expected_revision):
    with locked(session) as root:
        state = snapshot(root)
        if expected_revision != state["revision"]:
            raise ValueError("Investigation revision changed; reload before appending")
        row = dict(record)
        kind = row.get("kind")
        if (
            kind not in KINDS
            or not isinstance(row.get("text"), str)
            or not row["text"].strip()
        ):
            raise ValueError("Record needs a known kind and nonempty text")
        ident = row.setdefault("id", "r" + str(state["revision"] + 1))
        if not isinstance(ident, str) or not re.fullmatch(
            r"[A-Za-z0-9_.-]{1,100}", ident
        ):
            raise ValueError("Invalid record ID")
        old = next((r for r in state["records"] if r["id"] == ident), None)
        if old and old["kind"] != kind:
            raise ValueError("An existing record cannot change kind")
        row.setdefault("author", "unspecified")
        for field in ("support", "counter"):
            row.setdefault(field, [])
            if not isinstance(row[field], list):
                raise ValueError("Evidence references must be lists")
            for ref in row[field]:
                load_evidence(root, ref)
        if kind in STATES:
            row.setdefault("status", "open")
            if row["status"] not in STATES[kind]:
                raise ValueError("Invalid record status")
        if kind == "finding" and not row["support"]:
            raise ValueError("Findings require supporting evidence")
        if kind == "hypothesis" and row["status"] in {"supported", "refuted"}:
            required = "support" if row["status"] == "supported" else "counter"
            if not row[required]:
                raise ValueError(
                    "A supported/refuted hypothesis requires corresponding evidence"
                )
        if kind == "unknown" and row["status"] in {"resolved", "contradicted"}:
            required = "support" if row["status"] == "resolved" else "counter"
            if (
                not row[required]
                or not isinstance(row.get("resolution"), str)
                or not row["resolution"].strip()
            ):
                raise ValueError(
                    "Resolving/contradicting an unknown requires resolution text and evidence"
                )
        event = {
            "revision": state["revision"] + 1,
            "previous": state["history"][-1]["hash"] if state["history"] else None,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "record": row,
        }
        event["hash"] = digest(event)
        # Exclusive writer, one durable append; crash fragments are refused on the next read.
        import os

        with (root / "history.jsonl").open(
            "a", encoding="utf-8", newline="\n"
        ) as handle:
            handle.write(
                json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"
            )
            handle.flush()
            os.fsync(handle.fileno())
        return {"revision": event["revision"], "record": ident, "hash": event["hash"]}
