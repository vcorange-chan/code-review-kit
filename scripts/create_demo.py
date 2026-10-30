"""Create a public, synthetic 14-step document pipeline; no private project data."""

from pathlib import Path
import sys
import json
import copy

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / ".deps")]
from reviewkit.indexer import build_index
from reviewkit.rust import adapter_for
from reviewkit.business import extract_business
from reviewkit.storage import write_json


def create():
    folder = ROOT / "examples/document-pipeline"
    (folder / "src").mkdir(parents=True, exist_ok=True)
    stages = [
        ("accept", "接收文档"),
        ("open_source", "读取来源"),
        ("decode", "解码内容"),
        ("parse", "解析文档"),
        ("split", "拆分段落"),
        ("clean", "可选清理"),
        ("review", "可选复核"),
        ("annotate", "可选标注"),
        ("translate", "可选翻译"),
        ("preview", "可选预览"),
        ("commit", "提交结果"),
        ("collect", "汇总批次"),
        ("finish", "完成任务"),
        ("read_result", "查看结果"),
    ]
    lines = ["//! Synthetic pipeline for demonstrating review layouts, not a production importer."]
    nodes = []
    cards = {}
    edges = []
    for i, (name, title) in enumerate(stages, 1):
        start = len(lines) + 1
        lines.extend(
            [
                f"pub fn {name}(value: &str) -> Result<String, String> {{",
                f'    if value.is_empty() || value.contains("error_{i}") {{ return Err("{name} failed".into()); }}',
                "    Ok(value.to_owned())",
                "}",
            ]
        )
        ident = f"stage_{i}"
        nodes.append(
            {
                "id": ident,
                "label": name,
                "sources": [{"file": "src/lib.rs", "symbol": name, "label": title + "实现"}],
            }
        )
        kind = "degrade" if 6 <= i <= 10 else "error"
        branch = {
            "id": "optional" if kind == "degrade" else "failed",
            "kind": kind,
            "title": "可选处理不可用" if kind == "degrade" else "步骤失败",
            "state": "保留前一步结果" if kind == "degrade" else "停止流水线",
            "items": [
                {
                    "condition": f"输入包含 error_{i} 或为空",
                    "returns": f'Err("{name} failed")',
                    "handling": (
                        "保留原值并继续" if kind == "degrade" else "返回错误，不执行后续步骤"
                    ),
                }
            ],
        }
        cards["business::" + ident] = {
            "title": title,
            "scope": "合成文档工作流",
            "input_title": "前一步文档值",
            "inputs": ["传入字符串，不访问文件或网络。"],
            "output_title": "保留的文档值",
            "outputs": ["成功返回文档；可选步骤失败时由 run 保留旧值。"],
            "steps": [{"title": title, "detail": "检查当前步骤的失败标记；通过时返回文档值。"}],
            "state": "继续下一阶段" if i < 14 else "可读取最终结果",
            "branches": [branch],
            "notes": ["这是公开的合成示例，用于验证模板与流程图，不代表实际产品实现。"],
        }
        if kind == "degrade":
            edges.append(
                {
                    "from": ident,
                    "to": ident,
                    "kind": "resume",
                    "branch": "optional",
                    "port": "output",
                    "label": "保留原值，继续",
                }
            )
    lines.extend(
        ["pub fn run(input: &str) -> Result<String, String> {", "    let value = input.to_owned();"]
    )
    for i, (name, _) in enumerate(stages, 1):
        lines.append(
            f"    let value = {name}(&value)" + (".unwrap_or(value);" if 6 <= i <= 10 else "?;")
        )
    lines.extend(["    Ok(value)", "}"])
    (folder / "src/lib.rs").write_text("\n".join(lines) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "repository": ".",
        "title": "文档导入 · 14 阶段示例",
        "start_label": "提交文档",
        "end_label": "文档已就绪",
        "nodes": nodes,
        "edges": [
            {"from": a["id"], "to": b["id"], "kind": "success"} for a, b in zip(nodes, nodes[1:])
        ]
        + edges,
    }
    write_json(folder / "business.json", manifest)
    index = build_index(folder, adapter_for("rust"), ROOT / ".cache")
    facts = extract_business(index, manifest, 0, 64)
    for ident, card in cards.items():
        card["evidence_hash"] = facts["card_evidence"][ident]
    write_json(
        folder / "explanations.json",
        {"schema_version": 1, "evidence_hash": facts["evidence_hash"], "cards": cards},
    )
    english_titles = [
        "Accept document",
        "Read source",
        "Decode content",
        "Parse document",
        "Split paragraphs",
        "Optional cleanup",
        "Optional review",
        "Optional annotation",
        "Optional translation",
        "Optional preview",
        "Commit result",
        "Collect batch",
        "Complete task",
        "Read result",
    ]
    english_cards = copy.deepcopy(cards)
    for i, ((name, _), title) in enumerate(zip(stages, english_titles), 1):
        card = english_cards[f"business::stage_{i}"]
        optional = 6 <= i <= 10
        card.update(
            title=title,
            scope="Synthetic document workflow",
            input_title="Previous document value",
            inputs=["A string is passed; no file or network access."],
            output_title="Retained document value",
            outputs=[
                "Return the document on success; run retains the previous value if an optional step fails."
            ],
            steps=[
                {
                    "title": title,
                    "detail": "Check this step's failure marker; return the document value when it passes.",
                }
            ],
            state="Continue to the next stage" if i < 14 else "Final result is readable",
            notes=[
                "Public synthetic example for checking the template and workflow, not a production implementation."
            ],
        )
        branch = card["branches"][0]
        branch.update(
            title="Optional processing unavailable" if optional else "Step failed",
            state="Keep the previous result" if optional else "Stop the pipeline",
        )
        branch["items"] = [
            {
                "condition": f"Input contains error_{i} or is empty",
                "returns": f'Err("{name} failed")',
                "handling": (
                    "Retain the previous value and continue"
                    if optional
                    else "Return the error; skip subsequent steps"
                ),
            }
        ]
    write_json(
        folder / "explanations.en.json",
        {
            "schema_version": 1,
            "output_language": "en",
            "title": "Document import · 14-stage example",
            "flow": {"start_label": "Submit document", "end_label": "Document ready"},
            "evidence_hash": facts["evidence_hash"],
            "cards": english_cards,
        },
    )
    print("Created portable bilingual public example: examples/document-pipeline")


if __name__ == "__main__":
    create()
