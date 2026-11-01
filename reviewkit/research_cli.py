"""Thin CLI collection for source investigation; all behavior lives in shared modules."""

from contextlib import ExitStack
from pathlib import Path
from .engine import empty_facts, extract
from .dossier import build_dossier
from .evidence import evidence, page
from .i18n import resolve_language
from .indexer import build_index
from .languages import ADAPTERS, adapter_for
from .locate import locate
from .runtime import index_cache
from .source_identity import capture_source, commit_checkout
from .storage import digest, read_json, write_json
from . import investigation
from .research_render import render_research


def view_options(parser):
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--bytes", type=int, default=12000)


def add_parsers(sub, home):
    parser = sub.add_parser("locate", help="从业务词、文案、调用和注释找候选代码")
    parser.add_argument("--repo", required=True)
    parser.add_argument(
        "--query", action="append", required=True, help="可重复；按字面搜索，不调用模型"
    )
    parser.add_argument("--all", action="store_true", help="一个候选需命中全部检索词")
    parser.add_argument("--out", required=True)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--language", default="auto", choices=["auto", *ADAPTERS])
    parser.add_argument("--source-ref")
    parser.add_argument("--cache", default=str(index_cache(home)))
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--output-language", default="auto")
    parser.add_argument("--prompt")
    parser.add_argument("--session", help="明确把个人调查记录载入 HTML；默认不载入")
    parser = sub.add_parser(
        "dossier", help="从已有事实生成函数档案，或按栏目读取限额证据"
    )
    parser.add_argument("--facts", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--file")
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--facet",
        choices=[
            "signature",
            "branches",
            "errors",
            "returns",
            "calls",
            "callers",
            "types",
            "source",
        ],
    )
    view_options(parser)
    parser.add_argument("--output-language", default="auto")
    parser.add_argument("--prompt")
    parser.add_argument("--session")
    parser = sub.add_parser("investigate", help="持久保存调查与证据；不调用模型")
    parser.add_argument(
        "action", choices=["import", "record", "show", "evidence", "render"]
    )
    parser.add_argument("--session", required=True)
    parser.add_argument("--input", help="evidence bundle or record JSON")
    parser.add_argument("--expected-revision", type=int)
    parser.add_argument("--id")
    parser.add_argument(
        "--history", action="store_true", help="show 的完整历史栏目，仍分页"
    )
    parser.add_argument("--out", help="render 的 HTML 输出文件")
    parser.add_argument("--facts", help="render 可选的已捕获事实")
    parser.add_argument("--lookup", help="render 可选的 locate.json")
    parser.add_argument("--output-language", default="auto")
    parser.add_argument("--prompt")
    view_options(parser)


def artifacts(out, facts, lookup=None, symbols=None, session=None, language="zh"):
    dossiers, bundle = [], []
    for symbol in symbols if symbols is not None else facts["root_ids"]:
        dossier, items = build_dossier(facts, symbol)
        dossiers.append(dossier)
        bundle.extend(items)
    if lookup:
        bundle.append(
            evidence(
                "business.locate",
                {
                    "source_identity": lookup["source_identity"],
                    "scope_id": lookup["scope_id"],
                },
                lookup["candidates"],
                limits=lookup["limits"],
            )
        )
        packet = page(bundle[-1], budget=12000)
        packet["coverage"] = lookup["coverage"]
        # Keep coverage within the promised file budget too.
        from .evidence import byte_size

        while byte_size(packet) > 12000 and packet["rows"]:
            packet["rows"].pop()
            packet["next_offset"] = len(packet["rows"])
            packet["truncated"] = True
        write_json(out / "locate.packet.json", packet, compact=True)
    write_json(out / "dossiers.json", {"schema_version": 1, "dossiers": dossiers})
    write_json(out / "evidence.json", {"schema_version": 1, "evidence": bundle})
    render_research(
        out / "index.html",
        facts,
        lookup,
        dossiers,
        bundle,
        investigation.snapshot(session) if session else None,
        language,
    )
    return dossiers, bundle


def investigation_command(args):
    if args.action == "import":
        if not args.input:
            raise ValueError("import requires --input evidence.json")
        return investigation.import_evidence(args.session, read_json(args.input))
    if args.action == "record":
        if not args.input or args.expected_revision is None:
            raise ValueError("record requires --input and --expected-revision")
        return investigation.append(
            args.session, read_json(args.input), args.expected_revision
        )
    if args.action == "evidence":
        if not args.id:
            raise ValueError("evidence requires --id")
        return page(
            investigation.load_evidence(args.session, args.id),
            args.offset,
            args.limit,
            args.bytes,
        )
    state = investigation.snapshot(args.session)
    if args.action == "show":
        data = state["history"] if args.history else state["records"]
        item = evidence(
            "investigation.history" if args.history else "investigation.current",
            {
                "revision": state["revision"],
                "mixed_sources": state["mixed_sources"],
                "source_identity_count": len(state["source_identities"]),
            },
            data,
            basis="inferred",
            limits=state["limits"],
        )
        result = page(item, args.offset, args.limit, args.bytes)
        return result
    if not args.out:
        raise ValueError("render requires --out report.html")
    facts = read_json(args.facts) if args.facts else None
    lookup = read_json(args.lookup) if args.lookup else None
    if lookup and (
        not facts
        or lookup["source_identity"] != facts.get("source_snapshot", {}).get("id")
    ):
        raise ValueError("Lookup and facts source identities differ")
    dossiers, bundle = [], []
    if facts:
        for symbol in facts["root_ids"]:
            dossier, items = build_dossier(facts, symbol)
            dossiers.append(dossier)
            bundle.extend(items)
    language = resolve_language(args.output_language, args.prompt)
    render_research(args.out, facts, lookup, dossiers, bundle, state, language)
    return {
        "html": str(Path(args.out).resolve()),
        "revision": state["revision"],
        "includes_personal_records": True,
    }


def dispatch(args):
    if args.command == "investigate":
        return investigation_command(args)
    if args.command == "dossier":
        facts = read_json(args.facts)
        dossier, bundle = build_dossier(facts, args.symbol, args.file)
        out = Path(args.out).resolve()
        language = resolve_language(args.output_language, args.prompt)
        if args.facet:
            item = next(
                e
                for e in bundle
                if e["id"] == dossier["facets"][args.facet]["evidence"]
            )
            result = page(item, args.offset, args.limit, args.bytes)
            write_json(out / "dossier.packet.json", result, compact=True)
            return result
        artifacts(
            out,
            facts,
            symbols=[dossier["node"]],
            session=args.session,
            language=language,
        )
        return {
            "dossier": dossier,
            "html": str(out / "index.html"),
            "evidence": str(out / "evidence.json"),
        }
    if args.command != "locate":
        return None
    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        raise ValueError("Repository directory does not exist")
    with ExitStack() as resources:
        origin = None
        if args.source_ref:
            repo, origin = resources.enter_context(
                commit_checkout(repo, args.source_ref)
            )
        index = build_index(
            repo, adapter_for(args.language), Path(args.cache).resolve(), args.refresh
        )
        result = locate(index, args.query, args.limit, args.all)
        roots = [
            {"symbol": row["node_id"]} for row in result["candidates"] if row["node_id"]
        ]
        facts = (
            extract(index, roots, depth=1, max_nodes=max(64, len(roots)))
            if roots
            else empty_facts(index)
        )
        for row in result["candidates"]:
            facts["source_files"][row["file"]] = index["files"][row["file"]][
                "file_hash"
            ]
        capture_source(facts, repo, origin, index["adapter"])
        if origin:
            facts["repository"] = origin["repository"]
        language = resolve_language(args.output_language, args.prompt)
        result["output_language"] = facts["output_language"] = language
        result["source_identity"] = facts["source_snapshot"]["id"]
        result["origin"] = {
            k: facts["source_snapshot"][k]
            for k in ("mode", "commit", "git_files_verified")
        }
        result["id"] = "search_" + digest(
            {k: v for k, v in result.items() if k != "id"}
        )
        out = Path(args.out).resolve()
        write_json(out / "locate.json", result)
        write_json(out / "facts.json", facts)
        artifacts(out, facts, result, session=args.session, language=language)
        return {
            "locate": str(out / "locate.json"),
            "facts": str(out / "facts.json"),
            "html": str(out / "index.html"),
            "packet": str(out / "locate.packet.json"),
            "evidence": str(out / "evidence.json"),
            "candidates": len(result["candidates"]),
            "coverage": result["coverage"],
            "source_identity": result["source_identity"],
            "output_language": language,
        }
