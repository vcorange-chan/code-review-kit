"""Teaching lectures over extracted facts: line selection, revisions and bound discussions.

Code lines come only from the facts snapshot of each step's node; a lecture never carries
code text. Each step binds the node hash it was written against, so a changed source marks
the step for review instead of silently pairing old prose with new code.
"""

import datetime
import json
import re
from pathlib import Path
from .html_parts import e
from .i18n import LECTURE_EN, Translator, resolve_language
from .source_identity import verify_source

TEMPLATES = Path(__file__).resolve().parent / "templates"
VISIBLE_BUDGET = 20
KINDS = {"recorded": "明确记录", "inferred": "根据结果推断", "teaching": "教学上的解释"}
STEP_ID = re.compile(r"[A-Za-z0-9_-]+")


def node_id(item):
    return item.get("id", item["file"] + "::type::" + item["name"])


def fact_nodes(facts):
    return {node_id(item): item for item in [*facts["functions"], *facts.get("types", [])]}


def check_prose(where, prose):
    for reason in prose.get("reasons", []):
        if reason.get("kind") not in KINDS:
            raise ValueError(f"{where}: reasons.kind 只能是 {sorted(KINDS)}")
        if not reason.get("text") or not reason.get("support"):
            raise ValueError(f"{where}: 每条理由需要 text 与 support（依据）")
    if len(prose.get("decisions", [])) > 3:
        raise ValueError(f"{where}: 关键决策最多 3 处")
    if "change" in prose and "consider" in prose:
        raise ValueError(f"{where}: change 与 consider 只能选一个")
    if "progress" in prose and (not isinstance(prose["progress"], dict) or any(
        k not in {"seen", "focus", "next"} or not isinstance(v, str) for k, v in prose["progress"].items()
    )):
        raise ValueError("progress requires seen/focus/next text")
    if "behavior" in prose and (not isinstance(prose["behavior"], list) or any(
        not isinstance(b, dict) or not all(isinstance(b.get(k), str) for k in ("when", "result"))
        or ("next" in b and not isinstance(b["next"], str)) for b in prose["behavior"]
    )):
        raise ValueError("behavior requires when/result and optional next text")


def check_lecture(lecture):
    if lecture.get("schema_version") not in {1, 2} or not isinstance(lecture.get("id"), str):
        raise ValueError("讲义需要 schema_version:1/2 与字符串 id")
    if not STEP_ID.fullmatch(lecture["id"]):
        raise ValueError("讲义 id 只能使用字母、数字、下划线和连字符")
    seen = set()
    outline_ids = [s["id"] for s in lecture.get("outline", [])]
    if len(outline_ids) != len(set(outline_ids)) or any(not STEP_ID.fullmatch(s) for s in outline_ids):
        raise ValueError("Outline step IDs must be unique and stable")
    for step in lecture["steps"]:
        sid = step.get("id", "")
        if not STEP_ID.fullmatch(sid) or sid in seen:
            raise ValueError(f"步骤 id 无效或重复: {sid!r}")
        seen.add(sid)
        check_prose(sid, step)
        if lecture["schema_version"] == 2 and "change" in step:
            raise ValueError("Fixed-source lessons use progress/behavior, not before/after code changes")
        current = step.get("r", 1)
        revisions = set()
        for old in step.get("earlier", []):
            if not 1 <= old.get("r", 0) < current or old["r"] in revisions:
                raise ValueError(f"{sid}: earlier 的 r 必须小于当前 r={current}")
            revisions.add(old["r"])
            check_prose(f"{sid}.r{old['r']}", old)


def segments(step, first, last):
    """Every line of the node is either shown or inside exactly one gap."""
    owner = {}
    for a, b in step["show"]:
        for n in range(a, b + 1):
            if n in owner:
                raise ValueError(f"{step['id']}: L{n} 重复列出")
            owner[n] = None
    for gap in step["gaps"]:
        a, b = gap["lines"]
        for n in range(a, b + 1):
            if n in owner:
                raise ValueError(f"{step['id']}: L{n} 重复列出")
            owner[n] = gap
    missing = [n for n in range(first, last + 1) if n not in owner]
    extra = sorted(n for n in owner if not first <= n <= last)
    if missing or extra:
        raise ValueError(f"{step['id']}: 未覆盖 {missing[:5]}，越界 {extra[:5]}（节点 L{first}–{last}）")
    shown = {n for n, gap in owner.items() if gap is None}
    for decision in step.get("decisions", []):
        if decision["line"] not in shown:
            raise ValueError(f"{step['id']}: 关键决策 L{decision['line']} 位于折叠段")
    parts, n = [], first
    while n <= last:
        gap = owner[n]
        if gap is None:
            parts.append(("show", n))
            n += 1
        else:
            parts.append(("gap", gap))
            n = gap["lines"][1] + 1
    return parts, len(shown)


def read_discussion(path):
    if not path or not Path(path).is_file():
        return []
    records = []
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            record = json.loads(line)
            if not isinstance(record, dict) or not {"lecture", "step", "r", "kind"} <= record.keys():
                raise ValueError(f"讨论记录第 {number} 行缺少 lecture/step/r/kind")
            records.append(record)
    return records


def record_matches(lecture, step, record):
    if record["step"] != step["id"]:
        return False
    revision = step if record["r"] == step.get("r", 1) else next(
        (old for old in step.get("earlier", []) if old["r"] == record["r"]), None
    )
    if revision is None:
        return False
    source = revision.get("source_identity", lecture.get("source_identity"))
    return not (
        (record.get("source_identity") and source and record["source_identity"] != source)
        or (record.get("evidence_hash") and revision.get("evidence_hash") and record["evidence_hash"] != revision["evidence_hash"])
    )


def discuss(lecture, discussion_path, step_id, kind, quote, question=None, answer=None, text=None, revision=None):
    """Append one record; identity fields come from the lecture, never from the caller's guess."""
    check_lecture(lecture)
    step = next((s for s in lecture["steps"] if s["id"] == step_id), None)
    if step is None:
        raise ValueError(f"讲义中没有步骤 {step_id}")
    current = step.get("r", 1)
    revision = current if revision is None else revision
    selected = step if revision == current else next((s for s in step.get("earlier", []) if s["r"] == revision), None)
    if selected is None:
        raise ValueError(f"{step_id} 只有第 1–{current} 次讲解")
    if kind not in {"ask", "note"}:
        raise ValueError("Discussion kind must be ask or note")
    if kind == "ask" and not question:
        raise ValueError("提问需要 question")
    if kind == "note" and not text:
        raise ValueError("旁注需要 text")
    record = {
        "schema_version": 1,
        "lecture": lecture["id"],
        "step": step_id,
        "r": revision,
        "evidence_hash": selected.get("evidence_hash"),
        "source_identity": selected.get("source_identity", lecture.get("source_identity")),
        "kind": kind,
        "quote": quote or "",
        "time": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    }
    if kind == "ask":
        record.update({"question": question, "answer": answer or ""})
    else:
        record["text"] = text
    path = Path(discussion_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def accept_new(lecture, facts):
    """Bind steps written against the current facts; existing bindings are never replaced."""
    nodes = fact_nodes(facts)
    identity = verify_source(facts)
    if identity and not lecture.get("source_identity"):
        if any(s.get("evidence_hash") and s["evidence_hash"] != nodes[s["node"]]["hash"] for s in lecture["steps"] if s["node"] in nodes):
            raise ValueError("Cannot lock old explanations to different source evidence")
        lecture["source_identity"] = identity
    if lecture.get("source_identity") and lecture["source_identity"] != identity:
        raise ValueError("Lecture source identity differs; use its original facts snapshot")
    bound = []
    for step in lecture["steps"]:
        if not step.get("evidence_hash") and step["node"] in nodes:
            step["evidence_hash"] = nodes[step["node"]]["hash"]
            bound.append(step["id"])
    return bound


class LectureRenderer:
    def __init__(self, lecture, facts, records, language):
        self.lecture = lecture
        self.nodes = fact_nodes(facts)
        self.t = Translator(language, LECTURE_EN)
        self.records = records

    def row(self, sid, lines, first, n, marked=False):
        return (
            f'<div class="row{" mark" if marked else ""}" id="{sid}-L{n}"><span class="ln">{n}</span>'
            f'<span class="src">{e(lines[n - first]) or " "}</span></div>'
        )

    def gap(self, sid, lines, first, group):
        t = self.t
        a, b = group[0]["lines"][0], group[-1]["lines"][1]
        span = f"L{a}" if a == b else f"L{a}–{b}"
        rows = "".join(self.row(sid, lines, first, n) for n in range(a, b + 1))
        if group[0].get("out"):
            labels = "；".join(g["label"] for g in group)
            head = t("本课程不涉及") + "：" + e(labels) if len(group) == 1 else t("本课程不涉及（{} 段）").format(len(group))
            detail = "" if len(group) == 1 else f'<p class="gap-list">{e(labels)}</p>'
            return f'<details class="gap out"><summary><span class="gl">{span}</span>{head}</summary>{detail}{rows}</details>'
        return (
            f'<details class="gap"><summary><span class="gl">{span}</span>{e(group[0]["label"])}'
            f'<span class="ref">{e(group[0].get("ref", ""))}</span></summary>{rows}</details>'
        )

    def code(self, step, node):
        first, last = node["line"], node["end_line"]
        lines = node.get("source", "").split("\n")
        if len(lines) != last - first + 1:
            raise ValueError(f"{step['id']}: 事实缺少 {step['node']} 的完整源码快照，请重新提取")
        parts, visible = segments(step, first, last)
        marked = {d["line"] for d in step.get("decisions", [])}
        html, pending = [], []
        for kind, value in parts + [("end", None)]:
            if kind == "gap" and (not pending or (pending[-1].get("out") and value.get("out"))):
                pending.append(value)
                continue
            if pending:
                html.append(self.gap(step["id"], lines, first, pending))
                pending = []
            if kind == "gap":
                pending.append(value)
            elif kind == "show":
                html.append(self.row(step["id"], lines, first, value, value in marked))
        return "".join(html), visible

    def prose(self, sid, prose):
        t = self.t
        reasons = "".join(
            f'<li><span class="tag k-{e(r["kind"])}">{e(t(KINDS[r["kind"]]))}</span>{e(r["text"])}'
            f'<div class="support"><b>{t("依据")}</b>{e(r["support"])}</div>'
            + (f'<div class="support"><b>{t("局限")}</b>{e(r["limits"])}</div>' if r.get("limits") else "")
            + "</li>"
            for r in prose.get("reasons", [])
        )
        method = "".join(f"<li>{e(m)}</li>" for m in prose.get("method", []))
        decisions = "".join(
            f'<li><a href="#{sid}-L{d["line"]}" class="jump">L{d["line"]}</a>{e(d["text"])}'
            + (f'<div class="else"><b>{t("反事实比较")}</b>{e(d["otherwise"])}</div>' if d.get("otherwise") else "")
            + "</li>"
            for d in prose.get("decisions", [])
        )
        if "change" in prose:
            change = (
                f'<div class="block"><h3>{t("旧版对照 · 并非源码历史")}</h3><div class="change">'
                f'<div><b>{t("之前")}</b>{e(prose["change"]["before"])}</div>'
                f'<div><b>{t("现在")}</b>{e(prose["change"]["after"])}</div></div></div>'
            )
        elif "consider" in prose:
            items = "".join(f"<li>{e(c)}</li>" for c in prose["consider"])
            change = f'<div class="block"><h3>{t("考虑到这些情况")}</h3><ul>{items}</ul></div>'
        else:
            change = ""
        progress = prose.get("progress", {})
        if progress:
            change += '<div class="block progress"><h3>' + t("展示进度") + '</h3>' + ''.join(
                f'<p><b>{t(label)}</b>{e(progress[key])}</p>'
                for key, label in [("seen", "前面看过"), ("focus", "本次展开"), ("next", "接下来讲")]
                if progress.get(key)
            ) + '</div>'
        if prose.get("behavior"):
            change += '<div class="block behavior"><h3>' + t("程序行为 · 固定源码") + '</h3><ul>' + ''.join(
                f'<li><b>{e(b["when"])}</b> → {e(b["result"])}'
                + (f' → {e(b["next"])}' if b.get("next") else '') + '</li>' for b in prose["behavior"]
            ) + '</ul></div>'
        upper = (
            f"<h2>{e(prose['goal'])}</h2>"
            + (f'<div class="block"><h3>{t("为什么这样设计")}</h3><ul class="reasons">{reasons}</ul></div>' if reasons else "")
            + (f'<div class="block"><h3>{t("实现方法")}</h3><ul>{method}</ul></div>' if method else "")
        )
        lower = (
            f'<div class="block"><h3>{t("关键决策")}</h3><ol class="decisions">{decisions}</ol></div>' if decisions else ""
        ) + change
        return upper, lower

    def discussion(self, step):
        t = self.t
        mine = [r for r in self.records if record_matches(self.lecture, step, r)]
        if not mine:
            return ""
        asks = sum(r["kind"] == "ask" for r in mine)
        notes = len(mine) - asks
        current = step.get("r", 1)
        items = []
        for r in mine:
            older = f'<span class="rev">{t("针对第 {} 次讲解").format(r["r"])}</span>' if r["r"] != current else ""
            quote = f'<blockquote>{e(r.get("quote", ""))}</blockquote>' if r.get("quote") else ""
            if r["kind"] == "ask":
                body = (
                    f'<p><b>{t("问题")}</b>{e(r.get("question", ""))}</p>'
                    f'<p class="answer"><b>{t("回答")}</b>{e(r.get("answer", "")) or t("（尚无回答）")}</p>'
                )
            else:
                body = f'<p><b>{t("旁注")}</b>{e(r.get("text", ""))}</p>'
            items.append(f'<li class="d-{e(r["kind"])}" data-revision="{e(r["r"])}">{older}<span class="time">{e(r.get("time", ""))}</span>{quote}{body}</li>')
        return (
            f'<details class="discussion"><summary>{t("提问 {} · 旁注 {}").format(asks, notes)}</summary>'
            f'<ol>{"".join(items)}</ol></details>'
        )

    def step(self, step, index, total):
        from .tutor import prepare_step

        step = prepare_step(self.lecture, self.facts, step)
        t = self.t
        sid = step["id"]
        node = self.nodes[step["node"]]
        code, visible = self.code(step, node)
        bound = step.get("evidence_hash")
        state = "current" if bound == node["hash"] else ("stale" if bound else "unbound")
        badge = {
            "current": "",
            "stale": f'<span class="badge stale">{t("源码已变化 · 讲解待复核")}</span>',
            "unbound": f'<span class="badge stale">{t("尚未绑定证据")}</span>',
        }[state]
        current = step.get("r", 1)
        upper, lower = self.prose(sid, step)
        earlier_parts = []
        for old in step.get("earlier", []):
            old_id = f'{sid}-r{old["r"]}'
            old_code = ""
            if "show" in old and "node" in old:
                old = prepare_step(self.lecture, self.facts, old)
                old_code = '<div class="code">' + self.code({**old, "id": old_id}, self.nodes[old["node"]])[0] + '</div>'
            else:
                old_code = f'<p class="muted">{t("旧修订缺少完整视图，仅显示已有正文。")}</p>'
            old_upper, old_lower = self.prose(old_id, old)
            earlier_parts.append(
                f'<details class="earlier" data-revision="{old["r"]}" data-goal="{e(old["goal"])}"><summary>{t("第 {} 次讲解").format(old["r"])}'
                + (f'（{t("重讲原因")}：{e(old["reason"])}）' if old.get("reason") else "")
                + "</summary>" + old_upper + old_code + old_lower
                + f'<p>{e(old.get("place", ""))}</p>'
                + ''.join(f'<p><code>{e(s["name"])}</code> {e(s["where"])} {e(s["ref"])}</p>' for s in old.get("stubs", []))
                + "</details>"
            )
        earlier = "".join(earlier_parts)
        stubs = "".join(
            f'<li><code>{e(s["name"])}</code><span class="where">{e(s["where"])}</span><span class="ref">{e(s["ref"])}</span>'
            + (f'<span class="muted">{t("旧式手填签名 · 未核验")}</span>' if s.get("unverified_signature") else '') + '</li>'
            for s in step.get("stubs", [])
        )
        over = f'<span class="over">{t("超出建议行数")}</span>' if visible > VISIBLE_BUDGET else ""
        location = f'{node["file"]} L{node["line"]}–{node["end_line"]}'
        section = f"""
<section class="step" id="{sid}" data-step="{sid}" data-r="{current}" data-revision="{current}" data-goal="{e(step['goal'])}" data-loc="{e(location)}">
<header class="step-head"><span class="num">{t("第 {} / {} 步").format(index, total)}</span><span class="layer">{e(step.get('layer', ''))}</span>{f'<span class="retold">{t("第 {} 次讲解").format(current)}</span>' if current > 1 else ''}{badge}<span class="ver">{e(step.get('version', ''))}</span></header>
{upper}
<div class="block"><h3><code>{e(node['file'])}</code> · {e(node['name'])} · L{node['line']}–{node['end_line']}<span class="count">{t("显示 {} 行").format(visible)}</span>{over}</h3><div class="code">{code}</div></div>
{f'<div class="block"><h3>{t("本步只用签名")}</h3><ul class="stubs">{stubs}</ul></div>' if stubs else ''}
{lower}
<div class="block place"><h3>{t("放在哪里")}</h3><p>{e(step.get('place', ''))}</p></div>
{earlier}
{self.discussion(step)}
<footer class="step-foot"><button class="cmd primary" data-cmd="tutor next {self.lecture['id']}/{sid}.r{current}">{t("下一步")}</button><button class="cmd" data-cmd="tutor retell {self.lecture['id']}/{sid}.r{current}">{t("重讲")}</button></footer>
</section>"""
        return section, visible, state

    def intro(self):
        t = self.t
        lecture = self.lecture
        rows = [
            (t("业务"), lecture.get("business")),
            (t("贯穿全课的请求"), lecture.get("scenario")),
            (t("用户会观察到的变化"), lecture.get("observable")),
            (t("源码版本"), lecture.get("source")),
        ]
        html = "".join(f"<p><b>{label}</b>{e(value)}</p>" for label, value in rows if value)
        if lecture.get("invariants"):
            html += f'<p><b>{t("必须保持的约束")}</b></p><ul>' + "".join(f"<li>{e(x)}</li>" for x in lecture["invariants"]) + "</ul>"
        if lecture.get("notice"):
            html += f'<div class="notice">{e(lecture["notice"])}</div>'
        if lecture.get("not_covered"):
            html += f'<p class="muted"><b>{t("本讲义不覆盖")}</b>' + "、".join(e(x) for x in lecture["not_covered"]) + "</p>"
        snapshot = self.source_snapshot
        if snapshot:
            html += f'<p class="meta"><b>{t("快照身份")}</b>{e(snapshot["id"])} · {e(snapshot["mode"])}'
            if snapshot.get("commit"):
                html += f' · commit {e(snapshot["commit"])}'
            html += "</p>"
        if not snapshot or not lecture.get("source_identity"):
            html += f'<p class="notice">{t("来源未锁定：旧讲义兼容显示，不能据此确认指定提交。")}</p>'
        return html


def render_lecture(lecture, facts, target, discussion_path=None, output_language=None):
    check_lecture(lecture)
    identity = verify_source(facts)
    if lecture.get("source_identity") and lecture["source_identity"] != identity:
        raise ValueError("Lecture source identity differs; use its original facts snapshot")
    language = resolve_language(output_language or "auto", fallback=lecture.get("output_language", "zh"))
    records = read_discussion(discussion_path)
    matched = [r for r in records if r["lecture"] == lecture["id"]]
    renderer = LectureRenderer(lecture, facts, matched, language)
    renderer.facts = facts
    renderer.source_snapshot = facts.get("source_snapshot")
    t = renderer.t
    truncated = facts.get("limits", {}).get("truncated_nodes", [])
    missing = [s["node"] for s in lecture["steps"] if s["node"] not in renderer.nodes]
    if missing:
        hint = f"；本次提取因上限截断了 {len(truncated)} 个节点" if truncated else ""
        raise ValueError(f"讲义需要的节点不在事实中: {', '.join(missing)}{hint}。请用业务清单列出这些节点或调大 --max-nodes")
    sections, stats = [], {"stale_steps": [], "unbound_steps": [], "over_budget": []}
    total = len(lecture["steps"])
    for index, step in enumerate(lecture["steps"], 1):
        section, visible, state = renderer.step(step, index, total)
        sections.append(section)
        if state != "current":
            stats[state + "_steps"].append(step["id"])
        if visible > VISIBLE_BUDGET:
            stats["over_budget"].append(step["id"])
    unmatched = [r for r in matched if not any(record_matches(lecture, s, r) for s in lecture["steps"])]
    outline = "".join(
        f'<li><a href="#{s["id"]}"><span class="layer">{e(s.get("layer", ""))}</span>{e(s.get("short") or s["goal"])}</a></li>'
        for s in lecture["steps"]
    )
    warning = ""
    if stats["stale_steps"]:
        warning += f'<p>{t("这些步骤的源码已变化，讲解待复核：")}{e(", ".join(stats["stale_steps"]))}</p>'
    if unmatched:
        warning += f'<p>{t("部分讨论无法对应当前步骤、修订或源码身份，全文保留在页面底部。")}</p>'
    leftovers = "".join(
        f'<li>{e(r["step"])}.r{e(r["r"])} · {e(r.get("time", ""))}<blockquote>{e(r.get("quote", ""))}</blockquote>'
        f'<p>{e(r.get("question") or r.get("text", ""))}</p><p class="answer">{e(r.get("answer", ""))}</p></li>'
        for r in unmatched
    )
    values = {
        "LANG": "zh-CN" if language == "zh" else "en",
        "TITLE": e(lecture["title"]),
        "ID": e(lecture["id"]),
        "CSS": (TEMPLATES / "lecture.css").read_text(encoding="utf-8"),
        "JS": t.template((TEMPLATES / "lecture.js").read_text(encoding="utf-8")),
        "INTRO": renderer.intro(),
        "WARNING": warning,
        "OUTLINE": outline,
        "STEPS": "".join(sections),
        "UNMATCHED": f'<section class="unmatched"><h2>{t("未匹配的讨论")}</h2><ul>{leftovers}</ul></section>' if leftovers else "",
    }
    template = t.template((TEMPLATES / "lecture.html").read_text(encoding="utf-8"))
    page = re.sub(r"\{\{([A-Z]+)\}\}", lambda m: values[m.group(1)], template)
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(page, encoding="utf-8")
    stats.update(
        {
            "html": str(target.resolve()),
            "steps": total,
            "discussion_records": len(matched),
            "unmatched_discussion": len(unmatched),
            "other_lecture_records": len(records) - len(matched),
            "truncated_nodes": len(truncated),
            "output_language": language,
            "source_identity": identity,
            "source_locked": bool(identity and lecture.get("source_identity") == identity),
        }
    )
    return stats
