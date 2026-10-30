"""Rust syntax adapter. Candidate edges are deliberately not semantic proof."""

import re
from pathlib import Path
from .storage import digest
from .rust_context import (
    attached_attributes,
    context_catalog,
    lexical_context,
    nominal_type,
    owner_path,
    parameter_owner,
    parameter_hints,
    shadow_bindings,
)


def walk(node):
    yield node
    for child in node.children():
        yield from walk(child)


def location(node):
    r = node.range()
    return {"line": r.start.line + 1, "end_line": r.end.line + 1}


def nearest_function(node):
    return next((a for a in node.ancestors() if a.kind() == "function_item"), None)


def belongs(node, fn):
    n = nearest_function(node)
    return n is not None and n.range().start.index == fn.range().start.index


class RustAdapter:
    language = "rust"
    suffixes = (".rs",)
    version = "rust-syntax-10"
    sample = "fn probe() {}"

    def parse(self, text, file):
        from ast_grep_py import SgRoot

        root = SgRoot(text, "rust").root()
        malformed = bool(root.find_all(kind="ERROR"))
        catalog = context_catalog(root)
        functions = []
        for fn in root.find_all(kind="function_item"):
            ancestors = list(fn.ancestors())
            names = []
            for a in reversed(ancestors):
                if a.kind() == "mod_item" and a.field("name"):
                    names.append(a.field("name").text())
                elif a.kind() == "impl_item":
                    ty = a.field("type")
                    trait = a.field("trait")
                    if ty:
                        names.append(ty.text() + (" as " + trait.text() if trait else ""))
                elif a.kind() == "function_item":
                    names.append(a.field("name").text())
            name = fn.field("name").text()
            qualified = "::".join(names + [name])
            item = {
                "id": file + "::" + qualified,
                "name": name,
                "qualified": qualified,
                "aliases": [re.sub(r" as [^:]+(?=::)", "", qualified)],
                "file": file,
                **location(fn),
                "hash": digest(fn.text().encode("utf-8")),
                "context_hash": lexical_context(fn, catalog),
                "signature": fn.text().split("{", 1)[0].strip(),
                "parameter_types": parameter_hints(fn),
                "module_path": [
                    a.field("name").text()
                    for a in reversed(ancestors)
                    if a.kind() == "mod_item" and a.field("name")
                ],
                "parameters": fn.field("parameters").text(),
                "return_type": fn.field("return_type").text() if fn.field("return_type") else "()",
                "impl": next(
                    (
                        a.field("type").text()
                        for a in ancestors
                        if a.kind() == "impl_item" and a.field("type")
                    ),
                    None,
                ),
                "test": "/tests/" in "/" + file
                or any(
                    a.kind() == "mod_item" and a.field("name") and a.field("name").text() == "tests"
                    for a in ancestors
                ),
                "calls": [],
                "branches": [],
                "tries": [],
                "returns": [],
                "macros": [],
                "errors": [],
                "combinators": [],
                "statements": [],
                "parse_error": malformed,
            }
            body = fn.field("body")
            shadows = shadow_bindings(fn)
            for n in body.find_all(kind="call_expression"):
                if not belongs(n, fn):
                    continue
                f = n.field("function")
                if f and f.kind() == "generic_function":
                    f = f.field("function")
                if not f:
                    continue
                member = f.field("field") if f.kind() == "field_expression" else None
                callee = member.text() if member else f.text()
                receiver = f.field("value").text() if member and f.field("value") else None
                shadowed = bool(
                    receiver in item["parameter_types"]
                    and any(
                        offset < n.range().start.index and receiver in names
                        for offset, names in shadows
                    )
                )
                item["calls"].append(
                    {
                        **location(n),
                        "name": callee,
                        "short_name": callee.split("::")[-1],
                        "receiver": receiver[:160] if receiver else None,
                        "receiver_shadowed": shadowed,
                        "expression": n.text()[:500],
                        "truncated": len(n.text()) > 500,
                    }
                )
                if callee in {
                    "and_then",
                    "map_err",
                    "or_else",
                    "unwrap",
                    "expect",
                    "ok_or",
                    "ok_or_else",
                }:
                    item["combinators"].append({**location(n), "name": callee})
            for kind in [
                "if_expression",
                "match_expression",
                "while_expression",
                "loop_expression",
                "for_expression",
            ]:
                for n in body.find_all(kind=kind):
                    if not belongs(n, fn):
                        continue
                    condition = n.field("condition") or n.field("value")
                    arms = []
                    if kind == "match_expression":
                        block = n.field("body")
                        arms = (
                            [
                                a.text()[:500]
                                for a in block.named_children()
                                if a.kind() == "match_arm"
                            ]
                            if block
                            else []
                        )
                    item["branches"].append(
                        {
                            **location(n),
                            "kind": kind,
                            "condition": condition.text()[:800] if condition else "",
                            "has_else": bool(n.field("alternative")),
                            "arms": arms,
                        }
                    )
            for kind, key in [
                ("try_expression", "tries"),
                ("return_expression", "returns"),
                ("macro_invocation", "macros"),
            ]:
                for n in body.find_all(kind=kind):
                    if belongs(n, fn):
                        item[key].append({**location(n), "text": n.text()[:1200]})
            for n in body.find_all(kind="scoped_identifier"):
                if not belongs(n, fn) or not re.search(r"(?:Error|Failure|Err)::", n.text()):
                    continue
                parent = n.parent()
                text_node = parent if parent and parent.kind() == "call_expression" else n
                item["errors"].append(
                    {**location(n), "variant": n.text(), "expression": text_node.text()[:1200]}
                )
            item["statements"] = [
                {
                    **location(n),
                    "kind": n.kind(),
                    "text": n.text()[:1600],
                    "truncated": len(n.text()) > 1600,
                }
                for n in body.named_children()
                if n.kind() not in {"line_comment", "block_comment"}
            ]
            item["referenced_types"] = sorted(
                {n.text() for n in body.find_all(kind="type_identifier")}
                | {c["name"].split("::")[0] for c in item["calls"] if re.match(r"[A-Z]", c["name"])}
            )
            functions.append(item)
        # Duplicate conditional impls are never silently overwritten.
        counts = {}
        for f in functions:
            counts[f["id"]] = counts.get(f["id"], 0) + 1
        for f in functions:
            if counts[f["id"]] > 1:
                f["id"] += "@" + f["context_hash"][:12]
        types = []
        for kind in ["struct_item", "enum_item", "type_item"]:
            for n in root.find_all(kind=kind):
                if n.field("name"):
                    name = n.field("name").text()
                    modules = [
                        a.field("name").text()
                        for a in reversed(list(n.ancestors()))
                        if a.kind() == "mod_item" and a.field("name")
                    ]
                    qualified = "::".join(modules + [name])
                    types.append(
                        {
                            "name": name,
                            "id": file + "::type::" + qualified,
                            "qualified": qualified,
                            "kind": kind,
                            "file": file,
                            **location(n),
                            "hash": digest(
                                {"text": n.text(), "attributes": attached_attributes(n)}
                            ),
                            "text": n.text()[:8000],
                        }
                    )
        return {"functions": functions, "types": types, "parse_error": malformed}

    @staticmethod
    def candidates(call, caller, functions):
        return RustAdapter.resolve_call(call, caller, functions)["candidates"]

    @staticmethod
    def resolve_call(call, caller, functions):
        name = call["short_name"]
        found = [f for f in functions if f["name"] == name and not f["test"]]
        basis = "path_or_name"
        if call["receiver"]:
            if call["receiver"] == "self":
                found = [f for f in found if f["impl"] and owner_path(f) == owner_path(caller)]
                basis = "self_type"
            else:
                hint = caller.get("parameter_types", {}).get(call["receiver"])
                reason = "unknown_receiver_type"
                if call.get("receiver_shadowed"):
                    reason = "receiver_binding_may_be_shadowed"
                elif hint:
                    nominal = nominal_type(hint["type"])
                    if nominal is None or nominal in hint["generic_parameters"]:
                        reason = "polymorphic_receiver"
                    else:
                        expected = parameter_owner(hint["type"], caller)
                        if expected is None:
                            return {
                                "candidates": [],
                                "basis": "unresolved_receiver",
                                "reason": "qualified_receiver_requires_semantic_resolution",
                            }
                        found = [
                            f
                            for f in found
                            if f["impl"]
                            and owner_path(f) == expected
                            and crate(f["file"]) == crate(caller["file"])
                        ]
                        return {
                            "candidates": found,
                            "basis": "annotated_parameter_type",
                            "reason": "candidate" if found else "external_or_not_indexed",
                        }
                return {"candidates": [], "basis": "unresolved_receiver", "reason": reason}
        elif "::" in call["name"]:
            prefix = call["name"].rsplit("::", 1)[0].split("::")[-1]
            found = [f for f in found if Path(f["file"]).stem == prefix or f["impl"] == prefix]
        same = [f for f in found if crate(f["file"]) == crate(caller["file"])]
        result = [f for f in same if f["file"] == caller["file"]] or same or found
        return {
            "candidates": result,
            "basis": basis,
            "reason": "candidate" if result else "external_or_not_indexed",
        }

    @staticmethod
    def related_types(selected, index):
        text = "\n".join(
            f["parameters"]
            + " "
            + f["return_type"]
            + " "
            + " ".join(e["variant"] for e in f["errors"])
            + " "
            + " ".join(f.get("referenced_types", []))
            for f in selected
        )
        names = set(re.findall(r"\b[A-Z][A-Za-z0-9_]*\b", text))
        types = [t for item in index["files"].values() for t in item["types"]]
        same = lambda t: any(crate(t["file"]) == crate(f["file"]) for f in selected)
        for alias in [
            t for t in types if t["name"] in names and t["kind"] == "type_item" and same(t)
        ]:
            names.update(re.findall(r"\b[A-Z][A-Za-z0-9_]*\b", alias["text"]))
        return [t for t in types if t["name"] in names and same(t)]


def crate(file):
    parts = file.split("/")
    return "/".join(parts[:2]) if parts[0] in {"crates", "apps"} and len(parts) > 2 else ""


def adapter_for(language):
    from .languages import adapter_for as get_adapter

    return get_adapter(language)
