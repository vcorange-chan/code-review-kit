"""Fixed, escaped source-investigation UI. No model or server in the page."""

import json
import hashlib
from pathlib import Path
import re

from .html_parts import e, fold, p, pre
from .source_identity import verify_source
from .storage import digest
from .evidence import verify

LABELS = {
    "jump_source": ("定位源码", "Go to source"),
    "jump_evidence": ("查看引用证据", "Open cited evidence"),
    "detail": ("详情", "Details"),
    "title": ("代码调查工作台", "Source investigation"),
    "locate": ("业务定位", "Business locator"),
    "dossier": ("函数档案", "Function dossiers"),
    "investigation": ("调查记录", "Investigation records"),
    "filter": ("筛选候选函数或依据", "Filter candidates or clues"),
    "candidate": ("候选，不是已确认入口", "Candidate, not a confirmed entry"),
    "context": ("文件上下文，尚未定位函数", "File context, no function identified"),
    "open": ("查看函数档案", "Open function dossier"),
    "signals": ("定位依据", "Search signals"),
    "source": ("源码快照", "Source snapshot"),
    "limits": ("范围与限制", "Coverage and limits"),
    "signature": ("签名与输入", "Signature and inputs"),
    "branches": ("分支与条件", "Branches and conditions"),
    "errors": ("错误与传播", "Errors and propagation"),
    "returns": ("返回与输出", "Returns and outputs"),
    "calls": ("下游调用及未解析原因", "Calls and unresolved reasons"),
    "callers": ("上游候选与覆盖限制", "Caller candidates and coverage"),
    "types": ("提取范围内的相关类型", "Related types in the extracted scope"),
    "copy": ("复制提问上下文", "Copy question context"),
    "copied": ("已复制", "Copied"),
    "empty": (
        "没有结果；不代表业务不存在。",
        "No results; this does not prove absence.",
    ),
    "private": (
        "未载入个人调查记录。使用 --session 明确选择后才会加入页面。",
        "Personal investigation records excluded. Pass --session explicitly to include them.",
    ),
    "history": ("完整历史（保留旧判断）", "Full history (previous judgments retained)"),
    "mixed": (
        "注意：记录引用了多个源码身份，不能当成同一版本。",
        "Records refer to multiple source identities; do not treat them as one version.",
    ),
    "coverage": ("检索覆盖", "Search coverage"),
    "notice": (
        "离线静态证据；没有执行目标项目。分数是排序规则，不是概率。",
        "Offline static evidence; target project not executed. Scores are ranking rules, not probabilities.",
    ),
    "record": ("记录调查判断", "Record an investigation judgment"),
    "source_identity": ("源码身份", "Source identity"),
    "no_source": (
        "旧事实缺少可验证源码身份",
        "Legacy facts lack a verifiable source identity",
    ),
}


def render_research(
    output,
    facts=None,
    lookup=None,
    dossiers=(),
    evidence=(),
    investigation=None,
    language="zh",
):
    if language not in {"zh", "en"}:
        raise ValueError("Research output language must be zh or en")

    def t(key):
        return LABELS[key][language == "en"]

    def command(value):
        return (
            '<button data-copy="'
            + e(json.dumps(value, ensure_ascii=False))
            + '">'
            + e(t("copy"))
            + "</button>"
        )

    def data_rows(rows, source_prefix=None):
        return "".join(
            fold(
                ("L" + str(row["line"]) + " · " if "line" in row else "")
                + str(
                    next(
                        (
                            row[k]
                            for k in (
                                "name",
                                "condition",
                                "signature",
                                "category",
                                "kind",
                                "text",
                            )
                            if row.get(k)
                        ),
                        t("detail"),
                    )
                )[:120],
                (
                    '<button data-source-target="'
                    + e(source_prefix + "-L" + str(row["line"]))
                    + '">'
                    + e(t("jump_source"))
                    + "</button>"
                    if source_prefix and "line" in row
                    else ""
                )
                + pre(json.dumps(row, ensure_ascii=False, indent=2)),
            )
            for row in rows
        )

    identity = verify_source(facts) if facts else None
    if lookup and (
        lookup.get("source_identity") != identity
        or lookup.get("id")
        != "search_" + digest({k: v for k, v in lookup.items() if k != "id"})
    ):
        raise ValueError("Lookup content or source identity mismatch")
    records = {item["id"]: verify(item) for item in evidence}
    cards = []
    for row in (lookup or {}).get("candidates", []):
        target = "fn-" + hashlib.sha256(row["id"].encode()).hexdigest()[:20]
        signals = data_rows(row["signals"])
        title = t("candidate") if row["node_id"] else t("context")
        link = (
            ('<button data-dossier="' + target + '">' + e(t("open")) + "</button>")
            if row["node_id"]
            else ""
        )
        cards.append(
            '<article class="candidate card" data-search="'
            + e(json.dumps(row, ensure_ascii=False).casefold())
            + '">'
            + "<h2>"
            + e(row["name"])
            + "</h2>"
            + p(
                title
                + " · "
                + row["file"]
                + ":"
                + str(row["line"])
                + " · score "
                + str(row["score"])
            )
            + link
            + fold(t("signals") + " (" + str(row["hit_count"]) + ")", signals)
            + p("omitted_signals: " + str(row["omitted_signals"]))
            + "</article>"
        )
    lookup_body = p(t("empty")) if not cards else "".join(cards)
    if lookup:
        lookup_body = (
            fold(
                t("coverage"),
                pre(
                    json.dumps(
                        {
                            "queries": lookup["queries"],
                            **lookup["coverage"],
                            "limits": lookup["limits"],
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                ),
            )
            + lookup_body
        )
    function_cards = []
    for dossier in dossiers:
        if dossier["source_identity"] != identity:
            raise ValueError("Dossier and facts source identities differ")
        ident = "fn-" + hashlib.sha256(dossier["node"].encode()).hexdigest()[:20]
        facets = []
        for name, facet in dossier["facets"].items():
            item = records[facet["evidence"]]
            if (
                item["subject"].get("node") != dossier["node"]
                or item["subject"].get("source_identity") != identity
                or item["operation"] != "function." + name
            ):
                raise ValueError("Dossier facet evidence identity differs")
            if name == "source":
                body = (
                    '<pre class="source">'
                    + "".join(
                        '<span id="'
                        + ident
                        + "-L"
                        + str(r["line"])
                        + '"><b>'
                        + str(r["line"])
                        + "</b> "
                        + e(r["text"])
                        + "</span>"
                        for r in item["data"]
                    )
                    + "</pre>"
                )
            else:
                body = data_rows(
                    item["data"],
                    (
                        ident
                        if name in {"branches", "errors", "returns", "calls"}
                        else None
                    ),
                )
            payload = {
                "action": "review-investigation-question",
                "node": dossier["node"],
                "facet": name,
                "source_identity": dossier["source_identity"],
                "evidence": item["id"],
            }
            facets.append(
                '<div class="facet" id="'
                + item["id"]
                + '">'
                + fold(
                    t(name) + " (" + str(facet["count"]) + ")",
                    command(payload)
                    + p(item["id"])
                    + body
                    + fold(
                        t("limits"),
                        pre(json.dumps(item["limits"], ensure_ascii=False, indent=2)),
                    ),
                )
                + "</div>"
            )
        loc = dossier["location"]
        function_cards.append(
            '<article class="dossier card" id="'
            + ident
            + '"><h2>'
            + e(dossier["name"])
            + "</h2>"
            + p(loc["file"] + ":" + str(loc["line"]) + "–" + str(loc["end_line"]))
            + "".join(facets)
            + "</article>"
        )
    if investigation is None:
        journal = p(t("private"))
    else:
        journal = p("revision: " + str(investigation["revision"]))
        if investigation["mixed_sources"]:
            journal += p(t("mixed"))
        journal += "".join(
            fold(
                r["kind"] + " · " + r["id"] + " · " + r.get("status", ""),
                p(r["text"])
                + "".join(
                    (
                        (
                            '<button data-evidence-target="'
                            + ref
                            + '">'
                            + e(t("jump_evidence"))
                            + "</button>"
                        )
                        if ref in records
                        else command(
                            {"action": "review-investigation-evidence", "evidence": ref}
                        )
                    )
                    for ref in [*r.get("support", []), *r.get("counter", [])]
                )
                + pre(
                    json.dumps(
                        {k: v for k, v in r.items() if k != "text"},
                        ensure_ascii=False,
                        indent=2,
                    )
                ),
            )
            for r in investigation["records"]
        )
        journal += fold(
            t("history"),
            "".join(
                fold(
                    "r" + str(ev["revision"]) + " · " + ev["record"]["id"],
                    pre(json.dumps(ev, ensure_ascii=False, indent=2)),
                )
                for ev in investigation["history"]
            ),
        )
        journal += fold(
            t("limits"),
            pre(json.dumps(investigation["limits"], ensure_ascii=False, indent=2)),
        )
    journal += command(
        {
            "action": "review-investigation-record",
            "kinds": [
                "brief",
                "plan",
                "hypothesis",
                "finding",
                "unknown",
                "note",
                "handoff",
            ],
            "expected_revision": investigation["revision"] if investigation else 0,
        }
    )
    sections = {
        "locate": '<input id="filter" type="search" placeholder="'
        + e(t("filter"))
        + '" aria-label="'
        + e(t("filter"))
        + '">'
        + lookup_body,
        "dossier": "".join(function_cards) or p(t("empty")),
        "investigation": journal,
    }
    first = "locate" if lookup else "dossier" if dossiers else "investigation"
    nav = "".join(
        '<button data-tab="'
        + k
        + '" aria-pressed="'
        + str(k == first).lower()
        + '">'
        + e(t(k))
        + "</button>"
        for k in sections
    )
    content = "".join(
        '<section id="'
        + k
        + '"'
        + ("" if k == first else " hidden")
        + ">"
        + v
        + "</section>"
        for k, v in sections.items()
    )
    home = Path(__file__).parent / "templates"
    values = {
        "lang": language,
        "title": e(t("title")),
        "notice": e(t("notice")),
        "identity": e(t("source_identity") + ": " + (identity or t("no_source"))),
        "nav": nav,
        "content": content,
        "css": (home / "research.css").read_text(encoding="utf-8"),
        "js": (home / "research.js").read_text(encoding="utf-8"),
        "copied": e(t("copied")),
    }
    template = (home / "research.html").read_text(encoding="utf-8")
    html = re.sub(r"\{\{(\w+)\}\}", lambda match: values[match[1]], template)
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path
