"""Portable embedded source snapshots; local/editor/remote links are explicit options."""

from collections import defaultdict
from pathlib import Path
import hashlib
import os
import string
from urllib.parse import quote, urlsplit
from .html_parts import e, fold, p
from .storage import resolve_source


class SourceLinks:
    def __init__(self, facts, output, mode="embedded", template=None):
        self.repo = Path(facts["repository"])
        self.output = Path(output)
        self.mode = "template" if template is not None else mode
        self.template = template
        self.lines = defaultdict(dict)
        if self.mode not in {"embedded", "relative", "local", "template"}:
            raise ValueError("link-mode 仅支持 embedded/relative/local")
        if template is not None:
            fields = {"path", "absolute_path", "line", "end_line"}
            for _, field, spec, conversion in string.Formatter().parse(template):
                if field is not None and (field not in fields or spec or conversion):
                    raise ValueError(
                        "link-template 仅支持 path/absolute_path/line/end_line，无格式或属性表达式"
                    )
            if urlsplit(template).scheme.lower() not in {
                "",
                "https",
                "http",
                "file",
                "vscode",
                "vscode-insiders",
            }:
                raise ValueError("link-template 使用了不支持的 URL 协议")
        for item in facts["functions"]:
            self.add(item["file"], item["line"], item.get("source", ""))
            for source in item.get("sources", []):
                self.add(source["file"], source["line"], source.get("snippet", ""))
        for item in facts["types"]:
            self.add(item["file"], item["line"], item.get("text", ""))

    def add(self, file, first_line, source):
        for offset, text in enumerate(source.splitlines()):
            self.lines[file][first_line + offset] = text

    @staticmethod
    def target(file, line):
        key = hashlib.sha256(file.encode("utf-8")).hexdigest()[:16]
        return "source-" + key + "-L" + str(line)

    def reference(self, file, line, end_line=None):
        end_line = end_line or line
        label = file + ":" + str(line) + ("–" + str(end_line) if end_line != line else "")
        copy_text = file + ":" + str(line)
        marker = ""
        if self.mode == "embedded":
            target = self.target(file, line)
            href = "#" + target
            marker = ' data-snapshot="' + target + '"'
            self.lines[file].setdefault(line, "（此位置未纳入源码快照；可重新提取相关函数。）")
        elif self.mode == "local":
            href = resolve_source(self.repo, file).as_uri()
            copy_text = str(resolve_source(self.repo, file)) + ":" + str(line)
        elif self.mode == "relative":
            try:
                relative = os.path.relpath(
                    resolve_source(self.repo, file), self.output.parent.resolve()
                )
            except ValueError as error:
                raise ValueError(
                    "源码和报告不在同一盘符，无法生成相对链接；请使用 embedded 或 link-template"
                ) from error
            href = quote(Path(relative).as_posix(), safe="/")
        else:
            values = {
                "path": quote(file, safe="/"),
                "absolute_path": quote(
                    "/" + resolve_source(self.repo, file).as_posix().lstrip("/"), safe="/:"
                ),
                "line": line,
                "end_line": end_line,
            }
            href = self.template.format_map(values)
        return (
            '<a href="' + e(href) + '"' + marker + ">" + e(label) + "</a> "
            '<button class="copy" data-copy="' + e(copy_text) + '">复制位置</button>'
        )

    def item(self, item):
        return self.reference(item["file"], item["line"], item.get("end_line"))

    def snapshots(self):
        if self.mode != "embedded":
            return ""
        files = []
        for file, lines in sorted(self.lines.items()):
            rows = []
            previous = 0
            for number, text in sorted(lines.items()):
                if previous and number > previous + 1:
                    rows.append('<span class="source-gap">…</span>')
                rows.append(
                    '<span class="source-line" id="' + self.target(file, number) + '">'
                    '<span class="line-number">'
                    + str(number)
                    + "</span> <code>"
                    + e(text)
                    + "</code></span>"
                )
                previous = number
            files.append(fold(file, '<pre class="source-lines">' + "".join(rows) + "</pre>"))
        return (
            '<section id="source-view" class="inventory" hidden><h2>源码快照</h2>'
            '<button id="source-back">返回流程</button>'
            + p("只显示所选证据中的源码；行号为生成时快照。")
            + "".join(files)
            + "</section>"
        )
