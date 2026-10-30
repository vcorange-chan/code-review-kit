"""Business views bind multiple source anchors without pretending they are functions."""

from pathlib import Path
import copy
from .storage import digest, resolve_source
from .engine import all_functions, choose, extract


def anchor(repo, index, ref):
    if not isinstance(ref, dict) or not isinstance(ref.get("file"), str):
        raise ValueError("source 需要相对 file 路径")
    file = ref["file"].replace("\\", "/")
    path = resolve_source(repo, file)
    if index["files"].get(file, {}).get("parse_error"):
        raise ValueError("选定来源存在语法错误，拒绝作为完整证据: " + file)
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    symbol = ref.get("symbol")
    selected = None
    if symbol:
        symbols = all_functions(index) + [
            t for data in index["files"].values() for t in data["types"]
        ]
        selected = choose(symbols, symbol, file)
        offset = ref.get("offset", 0)
        end_offset = ref.get("end_offset")
        if not isinstance(offset, int) or (
            end_offset is not None and not isinstance(end_offset, int)
        ):
            raise ValueError("符号 offset/end_offset 必须是整数")
        start = selected["line"] + offset
        end = (
            selected["line"] + end_offset
            if end_offset is not None
            else start if "offset" in ref else selected["end_line"]
        )
        if not (1 <= start <= end <= len(lines)):
            raise ValueError("符号引用范围无效: " + file)
        fn = selected if "parameters" in selected else None
        mode = "symbol"
    else:
        start = ref.get("line", 1)
        end = ref.get("end_line") or start
        if (
            not isinstance(start, int)
            or not isinstance(end, int)
            or not (1 <= start <= end <= len(lines))
        ):
            raise ValueError("源码引用行范围无效: " + file)
        matches = [
            f
            for f in index["files"].get(file, {}).get("functions", [])
            if f["line"] <= start <= f["end_line"]
        ]
        fn = min(matches, key=lambda f: f["end_line"] - f["line"]) if matches else None
        mode = "legacy_line" if file in index["files"] else "context_range"
    # Bind the containing function; unindexed context anchors bind their stated range.
    text = (
        fn["source"]
        if fn and "source" in fn
        else (
            "\n".join(lines[fn["line"] - 1 : fn["end_line"]])
            if fn
            else "\n".join(lines[start - 1 : end])
        )
    )
    identity = selected["id"] if selected else file + ":" + str(start) + ":" + str(end)
    if selected and ("offset" in ref or "end_offset" in ref):
        identity += (
            ":offset:"
            + str(ref.get("offset", 0))
            + ":"
            + str(ref.get("end_offset", ref.get("offset", 0)))
        )
    content_hash = digest(
        {
            "symbol": selected["hash"] if selected else None,
            "function": digest(text.encode("utf-8")),
            "range": "\n".join(lines[start - 1 : end]),
        }
    )
    return {
        "file": file,
        "line": start,
        "end_line": end,
        "label": ref.get("label", "源码"),
        "kind": (
            fn.get("language", index["language"]) + "_function"
            if fn
            else selected.get("language", index["language"]) + "_type" if selected else "source_context"
        ),
        "anchor_mode": mode,
        "anchor_id": identity,
        "function_id": fn["id"] if fn else None,
        "hash": content_hash,
        "snippet": "\n".join(lines[start - 1 : min(len(lines), max(end, start + 7))]),
    }, fn


def validate_graph(nodes, edges):
    ids = [n["id"] for n in nodes]
    if len(ids) != len(set(ids)):
        raise ValueError("业务节点 id 不能重复")
    if any(
        not isinstance(i, str)
        or not i
        or any(
            c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in i
        )
        for i in ids
    ):
        raise ValueError("业务节点 id 仅使用字母、数字、下划线和连字符")
    expected = list(zip(ids, ids[1:]))
    success = []
    seen = set()
    for edge in edges:
        if not isinstance(edge, dict) or edge.get("from") not in ids or edge.get("to") not in ids:
            raise ValueError("流程边引用了不存在的节点")
        if edge.get("kind") not in {"success", "resume"}:
            raise ValueError("流程边 kind 必须是 success 或 resume")
        if edge["kind"] == "success":
            success.append((edge["from"], edge["to"]))
        else:
            if not isinstance(edge.get("branch"), str) or not edge["branch"]:
                raise ValueError("resume 边需要 branch id")
            if edge.get("port", "output") not in {"input", "output"}:
                raise ValueError("resume port 仅支持 input/output")
            key = (edge["from"], edge["branch"])
            if key in seen:
                raise ValueError("一个降级分支只能声明一个回到主流程的目标")
            seen.add(key)
    if success != expected:
        raise ValueError("直线主脉的 success 边必须依次连接全部节点；其他回边使用 resume")


def extract_business(index, manifest, depth, max_nodes):
    repo = Path(index["repository"])
    nodes = manifest["nodes"]
    edges = manifest.get(
        "edges",
        [{"from": a["id"], "to": b["id"], "kind": "success"} for a, b in zip(nodes, nodes[1:])],
    )
    validate_graph(nodes, edges)
    resolved = []
    selectors = []
    used = set()
    for node in nodes:
        refs = node.get("sources", [])
        if not isinstance(refs, list) or not refs:
            raise ValueError("业务视图节点需要至少一个 sources 引用")
        anchors = []
        primary = None
        for ref in refs:
            item, fn = anchor(repo, index, ref)
            anchors.append(item)
            if fn and primary is None:
                primary = fn
            if fn and fn["id"] not in used:
                used.add(fn["id"])
                selectors.append({"symbol": fn["id"]})
        resolved.append((node, anchors, primary))
    if len(selectors) > max_nodes:
        raise ValueError(f"多处引用包含 {len(selectors)} 个函数，请增加 --max-nodes")
    if selectors:
        facts = extract(index, selectors, depth, max_nodes)
    else:
        facts = {
            "schema_version": 1,
            "language": index["language"],
            "repository": str(repo),
            "generated_utc": "",
            "functions": [],
            "types": [],
            "edges": [],
            "callers": [],
            "macro_mentions": [],
            "bindings": {},
            "source_files": {},
            "card_evidence": {},
            "card_files": {},
            "index_stats": index["stats"],
            "limits": {
                "depth": depth,
                "max_nodes": max_nodes,
                "truncated_nodes": [],
                "resolution": "source_context_only",
            },
        }
        import datetime

        facts["generated_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    actual = {f["id"]: f for f in facts["functions"]}
    views = []
    for node, anchors, primary in resolved:
        if primary:
            view = copy.deepcopy(actual[primary["id"]])
        else:
            ref = anchors[0]
            view = {
                "file": ref["file"],
                "line": ref["line"],
                "end_line": ref["end_line"],
                "source": ref["snippet"],
                "parameters": "业务输入（见解释）",
                "return_type": "业务输出（见解释）",
                "signature": "源码上下文",
                "calls": [],
                "branches": [],
                "tries": [],
                "returns": [],
                "errors": [],
                "combinators": [],
                "macros": [],
                "statements": [],
                "parse_error": False,
            }
        alias = "business::" + node["id"]
        view.update(
            {
                "id": alias,
                "name": node.get("label", primary["name"] if primary else node["id"]),
                "qualified": node.get("label", node["id"]),
                "view": "business",
                "flow_id": node["id"],
                "sources": anchors,
                "function_id": primary["id"] if primary else None,
            }
        )
        local = {
            a["anchor_id"]: {
                "hash": a["hash"],
                "function": facts["card_evidence"].get(a["function_id"]),
            }
            for a in anchors
        }
        facts["card_evidence"][alias] = digest(
            {"sources": local, "outgoing": [e for e in edges if e["from"] == node["id"]]}
        )
        facts["card_files"][alias] = sorted(
            {a["file"] for a in anchors}
            | {file for a in anchors for file in facts["card_files"].get(a["function_id"], [])}
        )
        for a in anchors:
            facts["source_files"][a["file"]] = digest(resolve_source(repo, a["file"]).read_bytes())
        views.append(view)
    facts["functions"].extend(views)
    facts["root_ids"] = [v["id"] for v in views]
    facts["flow"] = {
        "nodes": [{"id": n["id"], "card_id": "business::" + n["id"]} for n in nodes],
        "edges": edges,
        "start_label": manifest.get("start_label", ""),
        "end_label": manifest.get("end_label", ""),
    }
    facts["evidence_hash"] = digest(facts["card_evidence"])
    return facts


def pin_sources(index, manifest):
    """Explicit migration produces a new manifest; it never rewrites explanations."""
    result = copy.deepcopy(manifest)
    changed = 0
    for node in result["nodes"]:
        for ref in node.get("sources", []):
            item, fn = anchor(Path(index["repository"]), index, ref)
            if not ref.get("symbol") and fn:
                ref["symbol"] = fn["id"]
                if item["line"] != fn["line"] or item["end_line"] != fn["end_line"]:
                    ref["offset"] = item["line"] - fn["line"]
                    ref["end_offset"] = item["end_line"] - fn["line"]
                ref.pop("line", None)
                ref.pop("end_line", None)
                changed += 1
    return result, changed
