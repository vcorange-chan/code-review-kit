"""Generate a fictional investigation, through the same public core used by skills."""

from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reviewkit.runtime import dependency_paths

sys.path[:0] = [str(path) for path in dependency_paths(ROOT)]
from reviewkit.cli import main as cli
from reviewkit.storage import read_json
from reviewkit import investigation


def build(out):
    out = Path(out).resolve()
    if (out / "session/history.jsonl").exists():
        raise ValueError(
            "Use a new output folder; demo never overwrites investigation history"
        )
    code = cli(
        [
            "locate",
            "--repo",
            str(ROOT / "examples/document-pipeline"),
            "--query",
            "Reading failed",
            "--query",
            "reduce_event",
            "--out",
            str(out),
            "--output-language",
            "zh",
        ]
    )
    if code:
        raise ValueError("Demo lookup failed")
    bundle = read_json(out / "evidence.json")
    investigation.import_evidence(out / "session", bundle)
    branches = next(
        e["id"] for e in bundle["evidence"] if e["operation"] == "function.branches"
    )
    records = [
        {
            "id": "goal",
            "kind": "brief",
            "author": "demo",
            "text": "定位文档读取失败时的界面状态处理，检查过期请求是否会覆盖新请求。",
        },
        {
            "id": "route",
            "kind": "plan",
            "author": "demo",
            "text": "先找界面文案，再读 reducer 的分支和返回；不执行目标项目。",
        },
        {
            "id": "old-request",
            "kind": "hypothesis",
            "author": "demo",
            "text": "旧请求的失败事件可能覆盖新请求状态。",
            "status": "open",
            "prediction": "不同 request_id 的事件仍会进入 failed 分支。",
        },
        {
            "id": "old-request",
            "kind": "hypothesis",
            "author": "demo",
            "text": "静态条件与预测相反：非 loading 或 request_id 不同时先返回原状态。",
            "status": "refuted",
            "counter": [branches],
            "limits": ["仅据静态分支，不是运行证明"],
        },
        {
            "id": "dispatch",
            "kind": "unknown",
            "author": "demo",
            "text": "事件是否都经过这个 reducer？当前局部证据无法确认。",
            "status": "open",
        },
        {
            "id": "handoff",
            "kind": "handoff",
            "author": "demo",
            "text": "已定位 reducer；下一步检查事件分发入口，保留未解析调用与当前待查项。",
            "support": [branches],
        },
    ]
    for revision, record in enumerate(records):
        investigation.append(out / "session", record, revision)
    code = cli(
        [
            "investigate",
            "render",
            "--session",
            str(out / "session"),
            "--facts",
            str(out / "facts.json"),
            "--lookup",
            str(out / "locate.json"),
            "--out",
            str(out / "personal.html"),
            "--output-language",
            "zh",
        ]
    )
    if code:
        raise ValueError("Demo rendering failed")
    return out / "personal.html"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    print(build(parser.parse_args().out))
