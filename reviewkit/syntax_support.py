"""Shared fact records for adapters; no language-specific dispatch rules here."""

import re
from .storage import digest


def node_location(node):
    span = node.range()
    return {"line": span.start.line + 1, "end_line": span.end.line + 1}


def function_record(file, qualified, line, end_line, source, context):
    return {
        "id": file + "::" + qualified,
        "name": qualified.split("::")[-1],
        "qualified": qualified,
        "aliases": [qualified.replace("::", ".")],
        "file": file,
        "line": line,
        "end_line": end_line,
        "hash": digest(source.encode("utf-8")),
        "context_hash": digest(context),
        "signature": "",
        "parameters": "",
        "return_type": "unspecified",
        "impl": None,
        "test": False,
        "calls": [],
        "branches": [],
        "tries": [],
        "returns": [],
        "errors": [],
        "combinators": [],
        "macros": [],
        "statements": [],
        "parse_error": False,
    }


def resolution(found=(), basis="lexical_scope", reason=None):
    found = list(found)
    return {
        "candidates": found,
        "basis": basis,
        "reason": reason or ("candidate" if found else "external_or_not_indexed"),
    }


def nominal(annotation):
    """Only a plain nominal path; no guessing through unions, generics or factories."""
    text = annotation.strip("'\"")
    return text if re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", text) else None


def unique_ids(functions):
    groups = {}
    for function in functions:
        groups.setdefault(function["id"], []).append(function)
    for group in groups.values():
        if len(group) < 2:
            continue
        seen = {}
        for function in group:
            key = function["hash"][:12]
            seen[key] = seen.get(key, 0) + 1
            function["id"] += "@" + key + ":" + str(seen[key])


def type_names(function):
    text = " ".join(
        [function["parameters"], function["return_type"], function.get("impl") or ""]
        + function.get("referenced_types", [])
    )
    return set(re.findall(r"\b[A-Z]\w*\b", text))
