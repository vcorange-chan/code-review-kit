"""Assemble the fixed page from small card, evidence and source-link renderers."""

from collections import defaultdict
from pathlib import Path
import re
from .storage import digest, resolve_source
from .engine import validate_explanations
from .card_render import CardRenderer, STATUS
from .html_parts import e, fold, p, pre, table
from .source_links import SourceLinks

TEMPLATES = Path(__file__).resolve().parent / "templates"


def changed_sources(facts):
    repo = Path(facts["repository"])
    changed = []
    for name, expected in facts["source_files"].items():
        path = resolve_source(repo, name)
        if not path.is_file() or digest(path.read_bytes()) != expected:
            changed.append(name)
    return changed


def call_relations(facts, links):
    functions = {f["id"]: f for f in facts["functions"]}
    candidates = []
    unresolved = defaultdict(list)
    for edge in facts["edges"]:
        if edge["candidates"]:
            candidates.append(
                (
                    e(edge["from"]),
                    e(edge["name"]),
                    e(edge.get("basis", "syntax_candidate")),
                    "<br>".join(e(x) for x in edge["candidates"]),
                )
            )
        else:
            key = (
                edge["from"],
                edge["name"],
                edge.get("receiver"),
                edge.get("reason", "unresolved"),
            )
            unresolved[key].append(edge["line"])
    rows = []
    for (owner, name, receiver, reason), lines in unresolved.items():
        file = functions[owner]["file"]
        rows.append(
            (
                e(owner),
                e(name),
                e(receiver or "—"),
                e(reason),
                " ".join(links.reference(file, line) for line in sorted(set(lines))),
            )
        )
    callers = table(
        ["调用者候选", "类别", "位置"],
        [
            (e(c["caller"]), "测试" if c["test"] else "生产候选", links.item(c))
            for c in facts["callers"]
        ],
    )
    macros = table(
        ["宏内提及（未展开）", "位置"],
        [(e(m["caller"]), links.item(m)) for m in facts["macro_mentions"]],
    )
    return (
        fold(
            "调用候选 · " + str(len(candidates)),
            table(["来源", "调用", "依据（非类型检查）", "候选目标"], candidates),
        )
        + fold(
            "未解析调用／接收者 · " + str(sum(len(v) for v in unresolved.values())),
            p(
                "未解析调用仍保留在图中。可能是接收者类型未知、外部函数、泛型或变量被遮蔽；不会静默丢弃。"
            )
            + table(["来源", "调用", "接收者", "未解析原因", "位置"], rows),
        )
        + fold("调用者与宏内提及", callers + macros)
    )


def inventory(facts, rows, links):
    limits = facts["limits"]
    boundary = (
        p("成功顺序来自业务清单。调用边是语法候选；未解析调用不等于没有调用。默认无运行验证。")
        + pre(facts["index_stats"])
        + p(
            f'追踪深度：{limits["depth"]}；节点上限：{limits["max_nodes"]}；超限未纳入：{len(limits["truncated_nodes"])}'
        )
        + p("解析错误文件：" + str(len(facts.get("parse_errors", []))))
        + p("上下文摘要保留可见导入、相关属性与宏。仍会对可见导入组等情况做保守判断。")
    )
    types = "".join(fold(t["name"], pre(t["text"]) + links.item(t)) for t in facts["types"])
    return (
        fold("按图索骥 · 查看顺序", table(["顺序", "函数／业务节点", "源码位置", "解释状态"], rows))
        + fold("调用关系与未解析项", call_relations(facts, links))
        + fold("相关类型与错误枚举", types)
        + fold("生成信息与边界", boundary)
    )


def terminal(flow, key, element_id):
    return (
        '<div class="terminal" id="' + element_id + '">' + e(flow[key]) + "</div>"
        if flow.get(key)
        else ""
    )


def render(
    facts, explanations, target, title="代码流程 Review", link_mode="embedded", link_template=None
):
    freshness = validate_explanations(explanations, facts)
    changed = changed_sources(facts)
    links = SourceLinks(facts, target, link_mode, link_template)
    renderer = CardRenderer(facts, links)
    cards = []
    rows = []
    for number, ident in enumerate(facts["root_ids"], 1):
        function = renderer.functions[ident]
        note = explanations.get("cards", {}).get(ident, {})
        files = facts.get("card_files", {}).get(ident, facts["source_files"])
        state = (
            "current" if freshness.get(ident) and not set(changed).intersection(files) else "stale"
        )
        if not note.get("steps"):
            state = "automatic"
        cards.append(renderer.card(number, function, note, state))
        rows.append((number, e(function["name"]), links.item(function), e(STATUS[state])))
    flow = facts.get("flow", {})
    values = {
        "TITLE": e(title),
        "CSS": (TEMPLATES / "review.css").read_text(encoding="utf-8"),
        "JS": (TEMPLATES / "review.js").read_text(encoding="utf-8"),
        "WARNING": (
            p("当前源码与事实快照不同，请重新提取：" + ", ".join(changed)) if changed else ""
        ),
        "CARDS": "".join(cards),
        "INVENTORY": inventory(facts, rows, links),
        "SNAPSHOTS": links.snapshots(),
        "COUNT": str(len(cards)),
        "GENERATED": e(facts["generated_utc"]),
        "START": terminal(flow, "start_label", "flow-start"),
        "END": terminal(flow, "end_label", "flow-end"),
    }
    template = (TEMPLATES / "review.html").read_text(encoding="utf-8")
    # A single substitution pass never interprets markers inside source or explanations.
    result = re.sub(r"\{\{([A-Z]+)\}\}", lambda match: values[match.group(1)], template)
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(result, encoding="utf-8")
    return {
        "cards": len(cards),
        "explained": sum(
            bool(explanations.get("cards", {}).get(i, {}).get("steps")) for i in facts["root_ids"]
        ),
        "stale_cards": [i for i, current in freshness.items() if not current],
        "source_changed": changed,
        "link_mode": links.mode,
        "unresolved_calls": sum(not x["candidates"] for x in facts["edges"]),
    }
