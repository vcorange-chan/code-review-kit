"""Function dossiers from already captured facts; no source reread or language parsing."""

from .engine import choose
from .evidence import evidence
from .source_identity import verify_source


def build_dossier(facts, symbol, file=None):
    identity = verify_source(facts)
    node = choose(facts["functions"], symbol, file)
    subject = {
        "source_identity": identity,
        "node": node["id"],
        "file": node["file"],
        "line": node["line"],
        "end_line": node["end_line"],
        "hash": node["hash"],
    }
    limits = ["syntax_candidates_not_runtime_proof", *node.get("analysis_limits", [])]
    if identity is None:
        limits.append("legacy_facts_without_verified_source_identity")
    incoming = [e for e in facts["edges"] if node["id"] in e["candidates"]]
    # The global name-match inventory was built for root names only.
    callers = [
        c
        for c in facts["callers"]
        if c["name"].split(".")[-1].split("::")[-1] == node["name"]
    ]
    records = {
        "signature": [
            {
                k: node.get(k)
                for k in (
                    "signature",
                    "parameters",
                    "return_type",
                    "language",
                    "imports",
                )
            }
        ],
        "branches": node["branches"],
        "errors": [
            {"category": k, **row}
            for k in ("errors", "tries", "combinators")
            for row in node[k]
        ],
        "returns": node["returns"],
        "calls": [e for e in facts["edges"] if e["from"] == node["id"]],
        "callers": [{"category": "name_match", **c} for c in callers]
        + [{"category": "selected_syntax_edge", **e} for e in incoming],
        "types": [
            {
                k: t.get(k)
                for k in ("id", "name", "file", "line", "end_line", "hash", "text")
            }
            for t in facts["types"]
        ],
        "source": [
            {"line": node["line"] + i, "text": text}
            for i, text in enumerate(node["source"].splitlines())
        ],
    }
    extra = {
        "callers": [
            "name_match_not_dispatch_proof",
            "root_name_inventory_only",
            "selected_edges_not_all_repository_callers",
        ],
        "types": ["related_types_from_extracted_scope_not_exact_field_dataflow"],
        "errors": ["explicit_syntax_only_implicit_failures_not_exhaustive"],
    }
    bundle = [
        evidence(
            "function." + facet,
            subject,
            rows,
            "observed" if facet == "source" else "derived",
            [*limits, *extra.get(facet, [])],
        )
        for facet, rows in records.items()
    ]
    dossier = {
        "schema_version": 1,
        "node": node["id"],
        "name": node["qualified"],
        "source_identity": identity,
        "location": {k: subject[k] for k in ("file", "line", "end_line")},
        "facets": {
            facet: {"evidence": record["id"], "count": len(record["data"])}
            for facet, record in zip(records, bundle)
        },
        "limits": limits,
    }
    return dossier, bundle
