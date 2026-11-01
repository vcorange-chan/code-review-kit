"""Business clues to syntax candidates. No model, execution, or dispatch claims."""

from collections import defaultdict
from .engine import all_functions
from .storage import digest

WEIGHTS = {
    "symbol": 100,
    "type": 75,
    "string": 60,
    "call": 45,
    "import": 25,
    "comment": 15,
    "path": 10,
}


def locate(index, queries, limit=20, match_all=False):
    terms = list(dict.fromkeys(q.strip() for q in queries if q.strip()))
    if not terms or len(terms) > 32 or any(len(q) > 1000 for q in terms):
        raise ValueError("Use 1–32 literal search terms of at most 1000 characters")
    if not 1 <= limit <= 200:
        raise ValueError("Candidate limit must be 1–200")
    functions = all_functions(index)
    by_file = defaultdict(list)
    for function in functions:
        by_file[function["file"]].append(function)
    found = {}
    hit_total = 0

    def owner(file, line):
        return min(
            (f for f in by_file[file] if f["line"] <= line <= f["end_line"]),
            key=lambda f: f["end_line"] - f["line"],
            default=None,
        )

    def add(file, line, end, kind, text, function=None):
        nonlocal hit_total
        matched = [q for q in terms if q.casefold() in text.casefold()]
        if not matched:
            return
        hit_total += 1
        function = function or (owner(file, line) if kind != "path" else None)
        ident = function["id"] if function else "context::" + file
        row = found.setdefault(
            ident,
            {
                "id": ident,
                "node_id": function["id"] if function else None,
                "name": function["qualified"] if function else file,
                "file": file,
                "line": function["line"] if function else line,
                "end_line": function["end_line"] if function else end,
                "source_hash": index["files"][file]["file_hash"],
                "language": index["files"][file]["language"],
                "matched_terms": [],
                "signals": [],
                "signal_kinds": [],
                "hit_count": 0,
                "score": 0,
                "parse_error": bool(index["files"][file]["parse_error"]),
                "status": "syntax_candidate" if function else "source_context_only",
            },
        )
        row["hit_count"] += 1
        for q in matched:
            if q not in row["matched_terms"]:
                row["matched_terms"].append(q)
        # One high score per signal kind, rather than inflating long functions by repetition.
        if kind not in row["signal_kinds"]:
            row["signal_kinds"].append(kind)
            row["score"] += WEIGHTS[kind]
        if len(row["signals"]) < 12:
            row["signals"].append(
                {
                    "kind": kind,
                    "line": line,
                    "end_line": end,
                    "terms": matched,
                    "preview": text[:500],
                    "preview_truncated": len(text) > 500,
                }
            )

    for file, data in sorted(index["files"].items()):
        add(file, 1, 1, "path", file)
        for function in data["functions"]:
            add(
                file,
                function["line"],
                function["end_line"],
                "symbol",
                function["qualified"],
                function,
            )
            for call in function["calls"]:
                add(
                    file,
                    call["line"],
                    call.get("end_line", call["line"]),
                    "call",
                    call["name"],
                    function,
                )
        for item in data["types"]:
            add(file, item["line"], item["end_line"], "type", item["name"])
        for site in data.get("search_sites", []):
            add(file, site["line"], site["end_line"], site["kind"], site["text"])
    candidates = [
        r
        for r in found.values()
        if not match_all or len(r["matched_terms"]) == len(terms)
    ]
    candidates.sort(key=lambda r: (-r["score"], r["file"], r["line"], r["id"]))
    for row in candidates:
        row["omitted_signals"] = row["hit_count"] - len(row["signals"])
    total = len(candidates)
    result = {
        "schema_version": 1,
        "queries": terms,
        "match": "all" if match_all else "any",
        "scope_id": digest(
            {
                "files": {f: d["file_hash"] for f, d in sorted(index["files"].items())},
                "adapter": index["adapter"],
            }
        ),
        "candidates": candidates[:limit],
        "coverage": {
            "indexed_files": len(index["files"]),
            "parse_error_files": [
                f for f, d in index["files"].items() if d["parse_error"]
            ],
            "total_candidates": total,
            "shown_candidates": min(total, limit),
            "candidate_limit": limit,
            "total_hits": hit_total,
            "truncated": total > limit,
        },
        "limits": [
            "literal_search_not_semantic_understanding",
            "ranking_is_not_probability",
            "candidates_not_business_entry_or_runtime_proof",
            "dynamic_strings_generated_code_unindexed_files_not_proven_absent",
        ],
    }
    result["id"] = "search_" + digest(result)
    return result
