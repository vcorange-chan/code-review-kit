"""Content-addressed, offline evidence and byte-bounded views, shared by clients."""

import json
import re
from .storage import digest

ID = re.compile(r"ev_[0-9a-f]{64}\Z")


def evidence(operation, subject, data, basis="derived", limits=()):
    if basis not in {"observed", "derived", "inferred"}:
        raise ValueError("Unknown evidence basis")
    item = {
        "schema_version": 1,
        "operation": operation,
        "subject": subject,
        "basis": basis,
        "data": data,
        "limits": list(limits),
    }
    return {"id": "ev_" + digest(item), **item}


def verify(item):
    ident = item.get("id", "")
    if (
        not isinstance(ident, str)
        or not ID.fullmatch(ident)
        or ident != "ev_" + digest({k: v for k, v in item.items() if k != "id"})
    ):
        raise ValueError("Evidence content hash mismatch")
    if item.get("basis") not in {"observed", "derived", "inferred"}:
        raise ValueError("Unknown evidence basis")
    return item


def byte_size(value):
    return len(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )


def page(item, offset=0, limit=20, budget=12000):
    """Never cut a row or silently skip an oversized row. Budget is bytes, not tokens."""
    verify(item)
    if offset < 0 or not 1 <= limit <= 200 or not 2048 <= budget <= 1000000:
        raise ValueError("Use offset >= 0, limit 1–200, bytes 2048–1000000")
    rows = item["data"] if isinstance(item["data"], list) else [item["data"]]
    if offset > len(rows):
        raise ValueError("Offset exceeds evidence length")
    result = {k: item[k] for k in ("id", "operation", "basis", "subject", "limits")}
    result.update(
        {
            "offset": offset,
            "total": len(rows),
            "rows": [],
            "next_offset": None,
            "truncated": False,
            "oversized_row": None,
        }
    )
    if byte_size(result) > budget:
        raise ValueError("Evidence metadata exceeds byte budget")
    for i in range(offset, min(offset + limit, len(rows))):
        trial = {
            **result,
            "rows": [*result["rows"], rows[i]],
            "next_offset": i + 1,
            "truncated": True,
        }
        # Reserve space for overflow metadata below.
        if byte_size(trial) + 100 > budget:
            result["oversized_row"] = (
                {"offset": i, "bytes": byte_size(rows[i])}
                if not result["rows"]
                else None
            )
            break
        result["rows"].append(rows[i])
    cursor = offset + len(result["rows"])
    result["truncated"] = cursor < len(rows)
    result["next_offset"] = cursor if result["truncated"] else None
    if byte_size(result) > budget:
        raise ValueError("Evidence view exceeds byte budget")
    return result
