import argparse
import importlib.metadata
import json
from pathlib import Path
import shutil
import sys
import time
from .storage import read_json, write_json
from .languages import ADAPTERS, adapter_for
from .indexer import build_index
from .engine import extract, make_packet, blank_explanations, validate_explanations
from .render import render
from .business import extract_business, pin_sources
from .build_cache import build_key, can_reuse
from .runtime import index_cache
from .i18n import resolve_language, explanation_language

HOME = Path(__file__).resolve().parent.parent


def output(value):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(value, ensure_ascii=False, separators=(",", ":")))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="离线提取 Rust/Python/Dart 函数或混合语言业务，生成折叠卡片 HTML。"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="检查本地依赖")
    for command in ["function", "business"]:
        p = sub.add_parser(command)
        if command == "function":
            p.add_argument("--repo", required=True)
            p.add_argument("--symbol", required=True)
            p.add_argument("--file")
            p.add_argument("--title")
        else:
            p.add_argument("--manifest", required=True)
        if command == "business":
            p.add_argument("--repo", help="覆盖清单仓库路径，供迁移/挂载环境使用")
        p.add_argument("--out", required=True)
        p.add_argument("--language", default="auto", choices=["auto", *ADAPTERS])
        p.add_argument("--depth", type=int, default=2)
        p.add_argument("--max-nodes", type=int, default=16)
        p.add_argument("--packet-bytes", type=int, default=24000)
        p.add_argument("--explanations")
        p.add_argument("--cache", default=str(index_cache(HOME)))
        p.add_argument("--refresh", action="store_true")
        p.add_argument("--link-mode", choices=["embedded", "relative", "local"], default="embedded")
        p.add_argument(
            "--link-template", help="源码链接模板，支持 {path}/{absolute_path}/{line}/{end_line}"
        )
    p = sub.add_parser("render", help="只用事实与解释重新生成 HTML")
    p.add_argument("--facts", required=True)
    p.add_argument("--explanations", required=True)
    p.add_argument("--html", required=True)
    p.add_argument("--title")
    p.add_argument("--link-mode", choices=["embedded", "relative", "local"], default="embedded")
    p.add_argument("--link-template")
    p = sub.add_parser("pin-sources", help="把可解析的旧业务行号锚点迁为符号锚点；不修改解释")
    p.add_argument("--manifest", required=True)
    p.add_argument("--repo")
    p.add_argument("--out", required=True)
    p.add_argument("--language", default="auto", choices=["auto", *ADAPTERS])
    p.add_argument("--cache", default=str(index_cache(HOME)))
    p = sub.add_parser("packet", help="为已选定节点导出有预算的 AI 证据包")
    p.add_argument("--facts", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--bytes", type=int, default=24000)
    p.add_argument("--symbol", help="只取 facts 中的某个符号，避免重复发送整个业务")
    p = sub.add_parser("lecture", help="用讲义 JSON 与事实快照生成逐步复现讲义 HTML")
    p.add_argument("--lecture", required=True)
    p.add_argument("--facts", required=True)
    p.add_argument("--html", help="默认与讲义同名的 .html")
    p.add_argument("--discussion", help="只追加的讨论记录 JSONL；省略时生成不含个人讨论的公开讲义")
    p.add_argument(
        "--accept-new", action="store_true", help="为尚未绑定的步骤写入当前证据摘要；已绑定的不改"
    )
    p = sub.add_parser("discuss", help="向讨论记录追加一条提问或旁注，身份字段取自讲义")
    p.add_argument("--lecture", required=True)
    p.add_argument("--discussion", required=True)
    p.add_argument("--step", required=True)
    p.add_argument("--kind", choices=["ask", "note"], required=True)
    p.add_argument("--quote", default="")
    p.add_argument("--revision", type=int, help="讨论针对的讲解修订；默认当前修订")
    p.add_argument("--question")
    p.add_argument("--answer")
    p.add_argument("--answer-file", help="从 UTF-8 文件读取完整回答，避免命令行转义")
    p.add_argument("--text", help="旁注原文")
    for name in ["function", "business", "render", "packet", "lecture"]:
        command_parser = sub.choices[name]
        command_parser.add_argument(
            "--output-language",
            default="auto",
            help="auto, zh/中文 or en/English; independent of source --language",
        )
        command_parser.add_argument(
            "--prompt", help="Natural-language request used by automatic output-language selection"
        )
    args = parser.parse_args(argv)
    started = time.perf_counter()
    try:
        if args.command == "doctor":
            from pathspec import GitIgnoreSpec

            if not GitIgnoreSpec.from_lines(["*.tmp"], backend="simple").match_file("probe.tmp"):
                raise ValueError("Ignore policy probe failed")
            parsers = {}
            for name in ADAPTERS:
                adapter = adapter_for(name)
                result = adapter.parse(adapter.sample, "probe" + adapter.suffixes[0])
                if result["parse_error"] or not result["functions"]:
                    raise ValueError("Parser probe failed: " + name)
                parsers[name] = "ok"
            output(
                {
                    "ok": True,
                    "python": sys.version.split()[0],
                    "ast_grep_py": importlib.metadata.version("ast-grep-py"),
                    "pathspec": importlib.metadata.version("pathspec"),
                    "rg": shutil.which("rg"),
                    "model_api": "未实现；运行完全离线",
                    "languages": list(ADAPTERS),
                    "parsers": parsers,
                }
            )
            return 0
        if args.command == "render":
            facts = read_json(args.facts)
            notes = read_json(args.explanations)
            language = resolve_language(
                args.output_language,
                args.prompt,
                notes.get("output_language", facts.get("output_language", "zh")),
            )
            output(
                {
                    "html": str(Path(args.html).resolve()),
                    **render(
                        facts,
                        notes,
                        args.html,
                        args.title or facts.get("title", "代码流程 Review"),
                        args.link_mode,
                        args.link_template,
                        language,
                    ),
                }
            )
            return 0
        if args.command == "lecture":
            from .lecture import accept_new, render_lecture

            lecture_path = Path(args.lecture).resolve()
            lecture = read_json(lecture_path)
            facts = read_json(args.facts)
            bound = accept_new(lecture, facts) if args.accept_new else []
            if bound:
                write_json(lecture_path, lecture)
            html = Path(args.html) if args.html else lecture_path.with_suffix(".html")
            language = None if args.output_language == "auto" else args.output_language
            if args.prompt:
                language = resolve_language(args.output_language, args.prompt)
            output({**render_lecture(lecture, facts, html, args.discussion, language), "bound_steps": bound})
            return 0
        if args.command == "discuss":
            from .lecture import discuss

            answer = (
                Path(args.answer_file).read_text(encoding="utf-8") if args.answer_file else args.answer
            )
            record = discuss(
                read_json(args.lecture),
                args.discussion,
                args.step,
                args.kind,
                args.quote,
                args.question,
                answer,
                args.text,
                args.revision,
            )
            output({"appended": True, "step": record["step"], "r": record["r"]})
            return 0
        if args.command == "pin-sources":
            path = Path(args.manifest).resolve()
            manifest = read_json(path)
            repo = Path(args.repo or manifest.get("repository", "."))
            if not repo.is_absolute():
                repo = (path.parent / repo).resolve()
            index = build_index(repo, adapter_for(args.language), Path(args.cache).resolve())
            result, count = pin_sources(index, manifest)
            # Keep the repository reference valid if the new manifest is written elsewhere.
            result["repository"] = str(repo)
            write_json(args.out, result)
            output(
                {
                    "manifest": str(Path(args.out).resolve()),
                    "pinned_sources": count,
                    "explanations_rebound": False,
                }
            )
            return 0
        if args.command == "packet":
            facts = read_json(args.facts)
            facts["output_language"] = resolve_language(
                args.output_language, args.prompt, facts.get("output_language", "zh")
            )
            if args.symbol:
                from .engine import choose

                node = choose(facts["functions"], args.symbol)
                facts = {**facts, "functions": [node], "root_ids": [node["id"]], "types": []}
            packet = make_packet(facts, args.bytes)
            path = Path(args.out)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(packet, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
            )
            output(
                {"packet": str(path.resolve()), "bytes": path.stat().st_size, "budget": args.bytes}
            )
            return 0
        if args.depth < 0 or args.max_nodes < 1 or args.packet_bytes < 2048:
            raise ValueError("depth 必须非负，max-nodes 至少 1，packet-bytes 至少 2048")
        if args.command == "business":
            manifest_path = Path(args.manifest).resolve()
            manifest = read_json(manifest_path)
            if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
                raise ValueError("业务清单需要 schema_version:1")
            repo = Path(args.repo or manifest.get("repository", "."))
            selectors = manifest["nodes"]
            title = manifest.get("title", "业务流程 Review")
            if not repo.is_absolute():
                repo = (manifest_path.parent / repo).resolve()
        else:
            manifest = None
            repo = Path(args.repo).resolve()
            selectors = [{"symbol": args.symbol, "file": args.file}]
            title = args.title or args.symbol
        if not repo.is_dir():
            raise ValueError("仓库目录不存在: " + str(repo))
        if not isinstance(selectors, list) or not selectors or len(selectors) > args.max_nodes:
            raise ValueError("业务 nodes 必须是非空数组，且数量不超过 max-nodes")
        business_views = args.command == "business" and all(
            isinstance(s, dict) and "id" in s for s in selectors
        )
        if not business_views and any(
            not isinstance(s, dict) or not isinstance(s.get("symbol"), str) for s in selectors
        ):
            raise ValueError("每个节点需要 symbol，可选 file")
        index = build_index(
            repo, adapter_for(args.language), Path(args.cache).resolve(), args.refresh
        )
        out = Path(args.out).resolve()
        out.mkdir(parents=True, exist_ok=True)
        notes_path = Path(args.explanations) if args.explanations else out / "explanations.json"
        existing_notes = read_json(notes_path) if notes_path.exists() else None
        args.resolved_output_language = resolve_language(
            args.output_language, args.prompt, (existing_notes or {}).get("output_language", "zh")
        )
        if not args.explanations:
            localized_notes = out / f"explanations.{args.resolved_output_language}.json"
            if localized_notes.exists() and (
                existing_notes is None
                or explanation_language(existing_notes) != args.resolved_output_language
            ):
                notes_path = localized_notes
                existing_notes = read_json(notes_path)
        key = build_key(args, index, manifest, existing_notes, HOME)
        if not args.refresh and can_reuse(out, key, index):
            stats = read_json(out / "build-stats.json")
            stats.update(
                {
                    "html_reused": True,
                    "index": index["stats"],
                    "elapsed_seconds": round(time.perf_counter() - started, 3),
                }
            )
            write_json(out / "build-stats.json", stats)
            output(stats)
            return 0
        facts = (
            extract_business(index, manifest, args.depth, args.max_nodes)
            if business_views
            else extract(index, selectors, args.depth, args.max_nodes)
        )
        facts["title"] = title
        facts["output_language"] = args.resolved_output_language
        facts["parse_errors"] = [p for p, data in index["files"].items() if data["parse_error"]]
        if any(f["parse_error"] for f in facts["functions"]):
            raise ValueError("选定函数所在文件存在语法错误，拒绝生成看似完整的卡片；请先修复源码")
        notes = existing_notes if existing_notes is not None else blank_explanations(facts)
        validate_explanations(notes, facts)
        packet = make_packet(facts, args.packet_bytes)
        report = render(
            facts,
            notes,
            out / "index.html",
            title,
            args.link_mode,
            args.link_template,
            args.resolved_output_language,
        )
        write_json(out / "facts.json", facts)
        # A separate seed never overwrites human/AI explanations on rebuild.
        write_json(out / "explanations.seed.json", blank_explanations(facts))
        legacy_notes = out / "explanations.json"
        if not legacy_notes.exists() or (
            args.explanations
            and explanation_language(read_json(legacy_notes)) == explanation_language(notes)
        ):
            write_json(out / "explanations.json", notes)
        write_json(out / f"explanations.{explanation_language(notes)}.json", notes)
        packet_path = out / "evidence-packet.json"
        packet_path.write_text(
            json.dumps(packet, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )
        stats = {
            "html": str(out / "index.html"),
            "facts": str(out / "facts.json"),
            "packet": str(packet_path),
            "packet_bytes": packet_path.stat().st_size,
            "functions_in_scope": len(facts["functions"]),
            **report,
            "index": facts["index_stats"],
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        }
        stats["html_reused"] = False
        write_json(
            out / "build-state.json",
            {
                "key": build_key(args, index, manifest, notes, HOME),
                "source_files": facts["source_files"],
            },
        )
        write_json(out / "build-stats.json", stats)
        output(stats)
        return 0
    except (ValueError, KeyError, OSError, ImportError) as error:
        output({"ok": False, "error": str(error)[:5000]})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
