"""Render one card from facts and plain-text explanations; no analysis rules here."""

from .html_parts import e, fold, p, pre, table
from .explanation_steps import step_location

STATUS = {
    "current": "源码解释 · 证据匹配（未运行验证）",
    "stale": "旧解释 · 待复核",
    "automatic": "自动提取 · 业务含义待补充",
}


class CardRenderer:

    def __init__(self, facts, links):
        self.t = links.t
        self.facts = facts
        self.functions = {f["id"]: f for f in facts["functions"]}
        self.links = links
        self.flow = facts.get("flow", {})
        self.stage_ids = {
            self.functions[ident].get("flow_id"): "card-" + str(number)
            for number, ident in enumerate(facts["root_ids"], 1)
        }

    def inputs(self, function, note):
        body = p(note["input"]) if note.get("input") else ""
        body += "".join((p(x) for x in note.get("inputs", [])))
        if function.get("view") != "business":
            body += pre(function["parameters"])
        return body

    def outputs(self, function, note):
        body = p(note.get("normal_output", ""))
        body += "".join((p(x) for x in note.get("outputs", [])))
        if function.get("view") != "business":
            body += pre(function["return_type"])
            for item in self.facts["types"]:
                if item["name"] in function["return_type"]:
                    body += fold(
                        self.t("返回相关类型 · ") + item["name"],
                        pre(item["text"]) + self.links.item(item),
                    )
        return body

    def steps(self, function, note):
        body = ""
        if note.get("steps"):
            for number, step in enumerate(note["steps"], 1):
                target = step_location(step, function["id"], self.functions)
                body_parts = []
                for key, label in [("actor", "执行者"), ("input", "进入此步")]:
                    if step.get(key):
                        body_parts.append(
                            "<p><strong>"
                            + e(self.t(label))
                            + "：</strong> "
                            + e(step[key])
                            + "</p>"
                        )
                body_parts.append(p(step["detail"]))
                for key, label in [("result", "本步结果"), ("next", "接下来")]:
                    if step.get(key):
                        body_parts.append(
                            "<p><strong>"
                            + e(self.t(label))
                            + "：</strong> "
                            + e(step[key])
                            + "</p>"
                        )
                body += fold(
                    f"{number:02d} · " + step["title"],
                    "".join(body_parts) + self.links.item(target),
                    expanded=any(step.get(key) for key in ["actor", "input", "result", "next"]),
                )
        else:
            body = p(self.t("以下为语法提取；业务阶段和实际执行顺序仍需解释。"))
            for number, statement in enumerate(function["statements"], 1):
                calls = [
                    c["name"]
                    for c in function["calls"]
                    if statement["line"] <= c["line"] <= statement["end_line"]
                ]
                title = " / ".join(dict.fromkeys(calls))[:100] or statement["kind"]
                body += fold(
                    f"{number:02d} · " + title,
                    pre(statement["text"])
                    + self.links.item({"file": function["file"], **statement}),
                )
        if note.get("state"):
            body += '<div class="state">' + e(note["state"]) + "</div>"
        return body

    def error_summary(self, note):
        items = note.get("errors", []) + [
            item for branch in note.get("branches", []) for item in branch["items"]
        ]
        if not items:
            return p(
                self.t("错误业务解释尚未补充。自动证据中的传播点和错误构造不代表完整错误路径。")
            )
        return table(
            [self.t("条件"), self.t("返回值"), self.t("收尾／下一步")],
            [(e(x["condition"]), e(x["returns"]), e(x["handling"])) for x in items],
        )

    def automatic_evidence(self, function):
        ref = lambda item: self.links.reference(
            function["file"], item["line"], item.get("end_line")
        )
        calls = table(
            [self.t("调用名称"), self.t("接收者（语法）"), self.t("位置")],
            [(e(c["name"]), e(c.get("receiver") or "—"), ref(c)) for c in function["calls"]],
        )
        branches = table(
            [self.t("语法"), self.t("条件"), self.t("其他分支")],
            [
                (
                    e(b["kind"]),
                    pre(b["condition"]),
                    p(self.t("含 else") if b["has_else"] else self.t("无 else"))
                    + "".join((pre(a) for a in b["arms"]))
                    + ref(b),
                )
                for b in function["branches"]
            ],
        )
        returned = "".join(
            (
                pre(x.get("text", x.get("expression", ""))) + ref(x)
                for x in function["returns"] + function["errors"]
            )
        )
        return (
            fold(self.t("调用表达式 · ") + str(len(function["calls"])), calls)
            + fold(self.t("分支 · ") + str(len(function["branches"])), branches)
            + fold(
                self.t("异常处理与传播点 · ") + str(len(function["tries"])),
                "".join((pre(x["text"]) + ref(x) for x in function["tries"])),
            )
            + fold(
                self.t("返回与错误构造"),
                returned or p(self.t("未提取到显式返回或命名错误构造；这不表示不会出错。")),
            )
            + fold(
                self.t("组合调用"),
                table(
                    [self.t("名称"), self.t("位置")],
                    [(e(c["name"]), ref(c)) for c in function["combinators"]],
                ),
            )
            + fold(
                self.t("宏（未展开）"),
                "".join((pre(x["text"]) for x in function["macros"])) or p(self.t("无宏调用。")),
            )
        )

    def sources(self, function):
        body = ""
        for source in function.get("sources", []):
            warning = (
                p(
                    self.t(
                        "旧式行号锚点：插入代码后可能定位到别处，建议使用 pin-sources 生成符号锚点。"
                    )
                )
                if source.get("anchor_mode") == "legacy_line"
                else ""
            )
            body += (
                '<div class="source"><strong>'
                + e(source.get("label", self.t("源码")))
                + "</strong>"
                + self.links.item(source)
                + warning
                + fold(self.t("引用上下文 · ") + source["kind"], pre(source["snippet"]))
                + "</div>"
            )
        return body + self.links.item(function) + pre(function.get("source", ""))

    def branch(self, function, branch):
        resume = next(
            (
                x
                for x in self.flow.get("edges", [])
                if x["kind"] == "resume"
                and x["from"] == function.get("flow_id")
                and (x["branch"] == branch["id"])
            ),
            None,
        )
        attrs = ' data-branch="' + e(branch["id"]) + '"'
        if resume:
            attrs += (
                ' data-resume="'
                + e(self.stage_ids[resume["to"]])
                + '" data-port="'
                + e(resume.get("port", "output"))
                + '"'
            )
        title = self.t("降级后继续") if branch["kind"] == "degrade" else self.t("错误／中止")
        detail = "".join(
            (fold(x["condition"], pre(x["returns"]) + p(x["handling"])) for x in branch["items"])
        )
        if resume:
            detail += (
                '<a class="resume-link" href="#'
                + e(self.stage_ids[resume["to"]])
                + '">'
                + e(resume.get("label", self.t("回到主流程")))
                + "</a>"
            )
        return (
            '<div class="branch '
            + branch["kind"]
            + '"'
            + attrs
            + '><div class="branch-kind">'
            + title
            + "</div>"
            + fold(branch.get("title", title), p(branch.get("state", "")) + detail)
            + "</div>"
        )

    def sides(self, function, note):
        result = ""
        for side in ["left", "right"]:
            groups = [
                b
                for b in note.get("branches", [])
                if b.get("side", "right" if b["kind"] == "degrade" else "left") == side
            ]
            legacy = [x for x in note.get("errors", []) if x.get("side", "left") == side]
            if groups:
                body = "".join((self.branch(function, b) for b in groups))
            elif legacy:
                body = self.t("<h3>错误输出</h3>") + "".join(
                    (fold(x["condition"], pre(x["returns"]) + p(x["handling"])) for x in legacy)
                )
            elif side == "left" and (not note.get("branches")) and (not note.get("errors")):
                body = self.t("<h3>错误输出</h3>") + p(self.t("待补充错误条件与返回值。"))
            else:
                body = self.t('<span class="muted">此侧无已解释分支</span>')
            result += '<aside class="fault ' + side + '">' + body + "</aside>"
        return result

    def card(self, number, function, note, state):
        label = note.get("title") if note.get("steps") else function["name"]
        heading = label if function.get("view") == "business" else function["name"]
        subtitle = function["name"] if function.get("view") == "business" else label
        implementation = (
            fold(self.t("功能实现"), self.steps(function, note))
            + fold(self.t("错误返回与降级"), self.error_summary(note))
            + fold(self.t("自动证据"), self.automatic_evidence(function))
            + fold(self.t("代码位置与源码"), self.sources(function))
        )
        if note.get("notes"):
            implementation += fold(self.t("补充说明与限制"), "".join((p(x) for x in note["notes"])))
        metadata = f"{number:02d} / " + note.get("scope", "") + " · " + self.t(STATUS[state])
        flow_id = e(function.get("flow_id", ""))
        return (
            f'<section class="stage" id="card-{number}" data-flow-id="{flow_id}" data-status="{state}">'
            + '<div class="spine"><div class="io input">'
            + fold(
                self.t("输入 · ") + note.get("input_title", self.t("函数参数")),
                self.inputs(function, note),
            )
            + '</div><article class="function"><div class="meta">'
            + e(metadata)
            + '</div><h2><button class="function-link">'
            + e(heading)
            + '</button></h2><p class="fn-name">'
            + e(subtitle)
            + "</p>"
            + implementation
            + "</article></div>"
            + '<div class="io stage-output">'
            + fold(
                self.t("正常输出 · ") + note.get("output_title", function["return_type"]),
                self.outputs(function, note),
            )
            + "</div>"
            + self.sides(function, note)
            + "</section>"
        )
