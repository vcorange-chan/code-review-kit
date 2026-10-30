import re
import datetime
from pathlib import Path
from .storage import digest, resolve_source
from .languages import adapter_for
from .i18n import Translator, explanation_language


def all_functions(index):
    return [f for item in index["files"].values() for f in item["functions"]]


def choose(functions, symbol, file=None):
    normalized = file.replace("\\", "/") if file else None
    found = [
        f
        for f in functions
        if (not normalized or f["file"] == normalized)
        and (
            symbol in {f["id"], f["qualified"], f["name"], *f.get("aliases", [])}
            or f["id"].endswith("::" + symbol)
        )
    ]
    if len(found) != 1:
        choices = "\n".join("  " + f["id"] for f in found[:30])
        raise ValueError(
            f"符号 {symbol!r} 匹配 {len(found)} 项；请补 --file 或完整符号。\n{choices}"
        )
    return found[0]


def extract(index, selectors, depth=2, max_nodes=16):
    adapter = adapter_for(index["language"])
    functions = all_functions(index)
    by_name = {}
    for f in functions:
        by_name.setdefault(f["name"], []).append(f)
    roots = [choose(functions, s["symbol"], s.get("file")) for s in selectors]
    selected = {}
    queue = [(r, 0) for r in roots]
    edges = []
    truncated = []
    while queue:
        f, level = queue.pop(0)
        if f["id"] in selected:
            continue
        if len(selected) >= max_nodes:
            truncated.append(f["id"])
            continue
        selected[f["id"]] = f
        for c in f["calls"]:
            resolution = adapter.resolve_call(c, f, by_name.get(c["short_name"], []))
            choices = resolution["candidates"]
            edges.append(
                {
                    "from": f["id"],
                    "line": c["line"],
                    "name": c["name"],
                    "receiver": c.get("receiver"),
                    "candidates": [t["id"] for t in choices],
                    "status": (
                        "unresolved"
                        if not choices
                        else "ambiguous" if len(choices) > 1 else "syntax_candidate"
                    ),
                    "basis": resolution["basis"],
                    "reason": resolution["reason"],
                }
            )
            if level < depth and len(choices) == 1:
                queue.append((choices[0], level + 1))
    root_names = {r["name"] for r in roots}
    callers = []
    macros = []
    for f in functions:
        for c in f["calls"]:
            if c["short_name"] in root_names:
                callers.append(
                    {
                        "caller": f["id"],
                        "file": f["file"],
                        "line": c["line"],
                        "name": c["name"],
                        "test": f["test"],
                        "status": "name_match_not_dispatch_proof",
                    }
                )
        for m in f["macros"]:
            if any(re.search(r"\b" + re.escape(n) + r"\s*\(", m["text"]) for n in root_names):
                macros.append({"caller": f["id"], "file": f["file"], **m})
    types = adapter.related_types(list(selected.values()), index)
    bindings = {}
    for f in selected.values():
        bindings[f["id"]] = digest({"function": f["hash"], "module_context": f["context_hash"]})
    for t in types:
        bindings[t.get("id", t["file"] + "::type::" + t["name"])] = t["hash"]
    # Every selected node and discovered related type is conservative evidence for each root.
    bundle = digest(bindings)
    card_evidence = {}
    card_files = {}
    for root in roots:
        seen = set()
        todo = [root["id"]]
        while todo:
            ident = todo.pop()
            if ident in seen or ident not in selected:
                continue
            seen.add(ident)
            todo.extend(c for edge in edges if edge["from"] == ident for c in edge["candidates"])
        relevant_types = adapter.related_types([selected[i] for i in seen], index)
        local = {i: bindings[i] for i in sorted(seen)}
        for t in relevant_types:
            local[t.get("id", t["file"] + "::type::" + t["name"])] = t["hash"]
        # Selection/resolution changes are also evidence changes, even with identical source text.
        local["__edges__"] = digest(
            [{k: v for k, v in e.items() if k != "line"} for e in edges if e["from"] in seen]
        )
        card_evidence[root["id"]] = digest(local)
        card_files[root["id"]] = sorted(
            {selected[i]["file"] for i in seen} | {t["file"] for t in relevant_types}
        )
    source_files = {f["file"] for f in selected.values()} | {t["file"] for t in types}
    for f in selected.values():
        lines = (
            resolve_source(Path(index["repository"]), f["file"])
            .read_text(encoding="utf-8-sig")
            .splitlines()
        )
        f["source"] = "\n".join(lines[f["line"] - 1 : f["end_line"]])
    facts = {
        "schema_version": 1,
        "language": index["language"],
        "repository": index["repository"],
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "root_ids": [r["id"] for r in roots],
        "functions": list(selected.values()),
        "types": types,
        "edges": edges,
        "callers": callers,
        "macro_mentions": macros,
        "bindings": bindings,
        "evidence_hash": bundle,
        "card_evidence": card_evidence,
        "card_files": card_files,
        "source_files": {p: index["files"][p]["file_hash"] for p in sorted(source_files)},
        "index_stats": index["stats"],
        "limits": {
            "depth": depth,
            "max_nodes": max_nodes,
            "truncated_nodes": truncated,
            "resolution": "syntax_candidates_not_complete_call_graph",
        },
    }
    return facts


def make_packet(facts, budget):
    """Hard UTF-8 byte cap. Never call a character count a measured token count."""
    import json

    packet = {
        "schema_version": 1,
        "purpose": "只返回 explanations.json；不要重写 HTML。业务顺序由清单给出。",
        "evidence_hash": facts["evidence_hash"],
        "root_ids": facts["root_ids"],
        "rules": [
            "有证据才填写；未知就写待判断。",
            "reference 用符号 ID，不固定行号。",
            "成功分支和所有错误条件需说明；调用候选不等于实际分派。",
        ],
        "functions": [],
        "types": [],
        "omitted": [],
    }
    language = facts.get("output_language", "zh")
    packet["output_language"] = language
    packet["presentation"] = {
        "title": facts.get("title", ""),
        "flow": {
            k: v for k, v in facts.get("flow", {}).items() if k in {"start_label", "end_label"}
        },
    }
    if language == "en":
        packet["purpose"] = (
            "Return explanation JSON only. Write all business prose in English; do not rewrite HTML."
        )
        packet["rules"] = [
            "Use evidence; preserve unknowns.",
            "Use symbol IDs for references.",
            "Explain success, errors and recovery. Candidate calls are not dispatch proof.",
        ]
    repo = Path(facts["repository"])

    def size():
        return len(json.dumps(packet, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

    seen = set()
    functions = sorted(facts["functions"], key=lambda f: 0 if f["id"] in facts["root_ids"] else 1)
    for f in functions:
        key = f.get("function_id") or f["id"]
        if key in seen:
            continue
        seen.add(key)
        item = {"id": f["id"], "signature": f["signature"], "source": f.get("source", "")}
        if f.get("view") == "business":
            item["label"] = f["name"]
            item["source_refs"] = [
                {k: s[k] for k in ["file", "line", "end_line", "label"]} for s in f["sources"]
            ]
        packet["functions"].append(item)
        if size() > budget:
            packet["functions"].pop()
            packet["omitted"].append(f["id"])
    for t in facts["types"]:
        packet["types"].append(t)
        if size() > budget:
            packet["types"].pop()
            packet["omitted"].append(t["name"])
    # Long symbol lists also count toward the budget.
    while size() > budget and packet["omitted"]:
        packet["omitted"].pop()
    packet["budget_bytes"] = budget
    packet["omissions_notice"] = (
        "Evidence is limited by the byte budget. Use packet --symbol for missing evidence. Full facts remain in facts.json."
        if language == "en"
        else "范围受字节预算限制，缺少证据时用 packet --symbol 指定节点另取。完整事实保存在 facts.json。"
    )
    while size() > budget and packet["functions"]:
        packet["functions"].pop()
    if size() > budget:
        raise ValueError("证据包预算过小，请至少使用 2048 字节或减少业务节点")
    return packet


def blank_explanations(facts):
    language = facts.get("output_language", "zh")
    t = Translator(language)
    return {
        "schema_version": 1,
        "output_language": language,
        "evidence_hash": facts["evidence_hash"],
        "cards": {
            i: {
                "evidence_hash": facts["card_evidence"][i],
                "title": t("待补充业务说明"),
                "input": "",
                "steps": [],
                "normal_output": "",
                "errors": [],
                "notes": [],
                "references": [i],
            }
            for i in facts["root_ids"]
        },
    }


def validate_explanations(value, facts):
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != 1
        or not isinstance(value.get("cards"), dict)
    ):
        raise ValueError("解释 JSON 需要 schema_version:1 和 cards 对象")
    explanation_language(value)
    if "title" in value and not isinstance(value["title"], str):
        raise ValueError("Explanation title must be text")
    if "flow" in value and (
        not isinstance(value["flow"], dict)
        or any(
            not isinstance(v, str)
            for k, v in value["flow"].items()
            if k in {"start_label", "end_label"}
        )
    ):
        raise ValueError("Explanation flow labels must be text")
    known = {f["id"] for f in facts["functions"]}
    for symbol, card in value["cards"].items():
        if symbol not in known:
            raise ValueError("解释包含未选定的函数 ID: " + symbol)
        if not isinstance(card, dict):
            raise ValueError("card 必须是对象")
        for key in [
            "title",
            "input",
            "input_title",
            "normal_output",
            "output_title",
            "state",
            "scope",
        ]:
            if key in card and not isinstance(card[key], str):
                raise ValueError(key + " 必须是文本")
        for key in ["steps", "errors"]:
            if not isinstance(card.get(key, []), list):
                raise ValueError(key + " 必须是数组")
        for step in card.get("steps", []):
            if (
                not isinstance(step, dict)
                or not isinstance(step.get("title"), str)
                or not isinstance(step.get("detail"), str)
            ):
                raise ValueError("step 需要 title、detail 文本")
        for error in card.get("errors", []):
            if not isinstance(error, dict) or any(
                not isinstance(error.get(k), str) for k in ["condition", "returns", "handling"]
            ):
                raise ValueError("error 需要 condition、returns、handling 文本")
            if error.get("side", "left") not in {"left", "right"}:
                raise ValueError("错误 side 只能是 left/right")
        branches = card.get("branches", [])
        if not isinstance(branches, list):
            raise ValueError("branches 必须是数组")
        seen = set()
        for branch in branches:
            if (
                not isinstance(branch, dict)
                or not isinstance(branch.get("id"), str)
                or not branch["id"]
                or branch["id"] in seen
            ):
                raise ValueError("分支需要唯一的非空 id")
            seen.add(branch["id"])
            if branch.get("kind") not in {"error", "degrade"}:
                raise ValueError("分支 kind 必须是 error/degrade")
            if any(not isinstance(branch.get(k, ""), str) for k in ["title", "state"]):
                raise ValueError("分支标题与状态必须是文本")
            if branch.get("side", "right" if branch["kind"] == "degrade" else "left") not in {
                "left",
                "right",
            }:
                raise ValueError("分支 side 必须是 left/right")
            if not isinstance(branch.get("items"), list):
                raise ValueError("分支需要 items 数组")
            for item in branch["items"]:
                if not isinstance(item, dict) or any(
                    not isinstance(item.get(k), str) for k in ["condition", "returns", "handling"]
                ):
                    raise ValueError("分支项需要 condition/returns/handling")
        for key in ["notes", "inputs", "outputs"]:
            if not isinstance(card.get(key, []), list) or any(
                not isinstance(x, str) for x in card.get(key, [])
            ):
                raise ValueError(key + " 必须是文本数组")
        if not isinstance(card.get("references", []), list) or any(
            not isinstance(x, str) for x in card.get("references", [])
        ):
            raise ValueError("references 必须是符号 ID 文本数组")
        refs = card.get("references", []) + [
            s.get("reference", symbol) for s in card.get("steps", [])
        ]
        if any(not isinstance(r, str) for r in refs):
            raise ValueError("reference 必须是符号 ID 文本")
        if any(r not in known for r in refs):
            raise ValueError("解释引用了不存在的符号")
    flow = facts.get("flow", {})
    for edge in flow.get("edges", []):
        if edge["kind"] != "resume":
            continue
        card = value["cards"].get("business::" + edge["from"])
        if card is None:
            continue  # A blank automatic report can still be rendered.
        branch = next((b for b in card.get("branches", []) if b["id"] == edge["branch"]), None)
        if branch is None and not card.get("steps"):
            continue
        if branch is None or branch["kind"] != "degrade":
            raise ValueError("resume 边必须指向已有的 degrade 分支")
    return {
        i: card.get("evidence_hash", value.get("evidence_hash"))
        == facts["card_evidence"].get(i, facts["evidence_hash"])
        for i, card in value["cards"].items()
    }
