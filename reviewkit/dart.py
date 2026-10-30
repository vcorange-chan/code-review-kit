"""Dart syntax adapter using the already-pinned ast-grep parser, without an SDK."""

import posixpath
import re
from .storage import digest
from .syntax_support import (
    function_record,
    nominal,
    resolution,
    type_names,
    unique_ids,
    node_location as location,
)

DECLARATIONS = {
    "function_declaration",
    "method_declaration",
    "local_function_declaration",
}
CLASSES = {
    "class_declaration",
    "mixin_declaration",
    "enum_declaration",
    "extension_declaration",
    "extension_type_declaration",
}
SIGNATURES = {
    "function_signature",
    "constructor_signature",
    "factory_constructor_signature",
    "getter_signature",
    "setter_signature",
    "operator_signature",
}


def own_nodes(node):
    for child in node.named_children():
        if child.kind() in DECLARATIONS | CLASSES | {"function_expression"}:
            continue
        yield child
        yield from own_nodes(child)


def direct_signature(node):
    if node.kind() in SIGNATURES:
        return node
    return next((n for n in own_nodes(node) if n.kind() in SIGNATURES), None)


def local_uri(file, uri):
    if ":" in uri or uri.startswith("/"):
        return None
    target = posixpath.normpath(posixpath.join(posixpath.dirname(file), uri))
    return None if target.startswith("../") else target


def import_allows(entry, name):
    return (
        not entry["show"] or name in re.findall(r"\w+", " ".join(entry["show"]))
    ) and name not in re.findall(r"\w+", " ".join(entry["hide"]))


class DartAdapter:
    language = "dart"
    suffixes = (".dart",)
    version = "dart-syntax-1"
    sample = "int probe() => 1;"

    def parse(self, text, file):
        from ast_grep_py import SgRoot

        root = SgRoot(text, "dart").root()
        malformed = bool(root.find_all(kind="ERROR"))
        directives = [
            n.text()
            for n in root.named_children()
            if n.kind()
            in {
                "import_or_export",
                "part_directive",
                "part_of_directive",
                "library_name",
            }
        ]
        imports = []
        parts = []
        for directive in directives:
            match = re.match(r"import\s+['\"]([^'\"]+)['\"]", directive)
            if match:
                alias = re.search(r"\bas\s+(\w+)", directive)
                imports.append(
                    {
                        "uri": match[1],
                        "file": local_uri(file, match[1]),
                        "alias": alias[1] if alias else None,
                        "conditional": bool(re.search(r"\bif\s*\(", directive)),
                        "show": re.findall(r"\bshow\s+([^;]+)", directive),
                        "hide": re.findall(r"\bhide\s+([^;]+)", directive),
                    }
                )
            match = re.match(r"part\s+(?:of\s+)?['\"]([^'\"]+)['\"]", directive)
            if match:
                target = local_uri(file, match[1])
                if target:
                    parts.append(target)
        class_nodes = [n for kind in CLASSES for n in root.find_all(kind=kind)]
        class_names = [n.field("name").text() for n in class_nodes if n.field("name")]
        declarations = [n for kind in DECLARATIONS for n in root.find_all(kind=kind)]
        # Abstract/external members and constructors without bodies are still entry points.
        declarations += [
            n
            for n in root.find_all(kind="declaration")
            if n.parent()
            and n.parent().kind() == "class_member"
            and direct_signature(n)
        ]
        declarations.sort(key=lambda n: n.range().start.index)
        constructor_names = set()
        for signature in root.find_all(kind="constructor_signature"):
            identifiers = [
                n.text() for n in signature.named_children() if n.kind() == "identifier"
            ]
            if identifiers:
                constructor_names.add(".".join(identifiers))
        functions = []
        for fn in declarations:
            signature = direct_signature(fn)
            if signature is None:
                continue
            name_node = signature.field("name")
            if name_node is None:
                continue
            name = name_node.text()
            if "constructor" in signature.kind():
                names = [
                    n.text()
                    for n in signature.named_children()
                    if n.kind() == "identifier"
                ]
                name = ".".join(names) or name
            elif signature.kind() in {"getter_signature", "setter_signature"}:
                name = (
                    "get:" if signature.kind() == "getter_signature" else "set:"
                ) + name
            ancestors = list(reversed(list(fn.ancestors())))
            owners = [a for a in ancestors if a.kind() in CLASSES and a.field("name")]
            enclosing = [
                direct_signature(a) for a in ancestors if a.kind() in DECLARATIONS
            ]
            nesting = [
                s.field("name").text() for s in enclosing if s and s.field("name")
            ]
            class_owner = "::".join(a.field("name").text() for a in owners) or None
            # A local function inside a method is not itself an implicit-this method.
            owner = class_owner if not nesting else None
            qualified = "::".join(
                ([class_owner] if class_owner else []) + nesting + [name]
            )
            owner_headers = [a.text().split("{", 1)[0] for a in owners]
            context = {"directives": directives, "owners": owner_headers}
            item = function_record(
                file,
                qualified,
                location(fn)["line"],
                location(fn)["end_line"],
                fn.text(),
                context,
            )
            body = fn.field("body")
            parameters = signature.field("parameters")
            hints = {}
            param_names = []
            if parameters:
                for p in parameters.find_all(kind="formal_parameter"):
                    ident = p.field("name") or next(
                        (c for c in p.named_children() if c.kind() == "identifier"),
                        None,
                    )
                    ty = next(
                        (n for n in p.named_children() if n.kind() == "type"), None
                    )
                    if ident:
                        param_names.append(ident.text())
                        if ty:
                            hints[ident.text()] = ty.text()
            nodes = list(own_nodes(body)) if body else []
            generic = [
                next(
                    (
                        c.text()
                        for c in n.named_children()
                        if c.kind() == "type_identifier"
                    ),
                    n.text(),
                )
                for a in [*owners, signature]
                for n in a.find_all(kind="type_parameter")
            ]
            fields = []
            for class_node in owners:
                class_body = class_node.field("body")
                for member in class_body.named_children() if class_body else []:
                    declaration = next(
                        (
                            c
                            for c in member.named_children()
                            if c.kind() == "declaration"
                        ),
                        None,
                    )
                    if declaration and not direct_signature(declaration):
                        fields.extend(
                            n.text()
                            for n in declaration.find_all(kind="initialized_identifier")
                            if n.field("name")
                        )
                        fields.extend(
                            n.text() for n in declaration.find_all(kind="identifier")
                        )
            item.update(
                {
                    "language": "dart",
                    "signature": (
                        " ".join(
                            c.text()
                            for c in fn.named_children()
                            if c.range().end.index <= body.range().start.index
                        )
                        if body
                        else fn.text()
                    ),
                    "parameters": parameters.text() if parameters else "()",
                    "return_type": (
                        signature.field("return_type").text()
                        if signature.field("return_type")
                        else (
                            class_owner
                            if "constructor" in signature.kind()
                            else "unspecified"
                        )
                    ),
                    "impl": owner,
                    "parameter_types": hints,
                    "parameter_names": param_names,
                    "imports": imports,
                    "parts": parts,
                    "local_classes": class_names,
                    "generic_parameters": generic,
                    "static": bool(re.match(r"\s*(?:external\s+)?static\b", fn.text())),
                    "constructor": "constructor" in signature.kind(),
                    "async": bool(body and re.match(r"\s*async\b", body.text())),
                    "test": file.endswith("_test.dart"),
                    "assigned_names": [],
                    "field_names": fields,
                    "referenced_types": sorted(
                        {n.text() for n in fn.find_all(kind="type_identifier")}
                    ),
                    "parse_error": malformed,
                    "analysis_limits": [
                        "sdk_types_extensions_dynamic_dispatch_not_resolved",
                        "implicit_exceptions_not_enumerated",
                        "closure_bodies_not_expanded",
                    ],
                }
            )
            assigned = set()
            for n in nodes:
                if n.kind() in {
                    "initialized_variable_definition",
                    "initialized_identifier",
                    "assignment_expression",
                }:
                    left = (
                        n.field("left")
                        or n.field("name")
                        or next(
                            (
                                c
                                for c in n.named_children()
                                if c.kind() in {"identifier", "assignable_expression"}
                            ),
                            None,
                        )
                    )
                    if left and re.fullmatch(r"\w+", left.text()):
                        assigned.add(left.text())
                if n.kind() == "call_expression":
                    callee = n.field("function")
                    if not callee:
                        continue
                    # A generic call still names the underlying function/member.
                    if callee.kind() in {"generic_function", "type_cast_expression"}:
                        callee = callee.field("function") or callee
                    member = (
                        callee.field("property")
                        if callee.kind() == "member_expression"
                        else None
                    )
                    receiver = callee.field("object") if member else None
                    short = member.text() if member else callee.text()
                    call_name = callee.text()
                    item["calls"].append(
                        {
                            **location(n),
                            "name": call_name,
                            "short_name": short,
                            "lookup_name": (
                                call_name if call_name in constructor_names else short
                            ),
                            "receiver": receiver.text() if receiver else None,
                            "expression": n.text()[:500],
                            "truncated": len(n.text()) > 500,
                        }
                    )
                if n.kind() in {
                    "if_statement",
                    "for_statement",
                    "while_statement",
                    "do_statement",
                    "switch_statement",
                    "switch_expression",
                    "conditional_expression",
                }:
                    condition = n.field("condition") or next(
                        iter(n.named_children()), None
                    )
                    arms = [
                        a.text()[:800]
                        for a in n.find_all(kind="switch_statement_case")
                        + n.find_all(kind="switch_expression_case")
                        + n.find_all(kind="switch_statement_default")
                    ]
                    item["branches"].append(
                        {
                            **location(n),
                            "kind": n.kind(),
                            "condition": condition.text()[:800] if condition else "",
                            "has_else": bool(n.field("alternative")),
                            "arms": arms,
                        }
                    )
                if n.kind() in {"try_statement", "await_expression"}:
                    item["tries"].append({**location(n), "text": n.text()[:1600]})
                    if n.kind() == "try_statement":
                        item["branches"].append(
                            {
                                **location(n),
                                "kind": "try_statement",
                                "condition": "exception handling",
                                "has_else": False,
                                "arms": [
                                    c.text()[:800]
                                    for c in n.named_children()
                                    if c.kind()
                                    in {"type", "catch_clause", "finally_clause"}
                                ],
                            }
                        )
                if n.kind() == "return_statement":
                    item["returns"].append({**location(n), "text": n.text()[:1200]})
                if n.kind() in {
                    "throw_expression",
                    "rethrow_statement",
                    "assert_statement",
                }:
                    item["errors"].append(
                        {
                            **location(n),
                            "variant": n.text().split("(", 1)[0],
                            "expression": n.text()[:1200],
                        }
                    )
            item["assigned_names"] = sorted(assigned)
            if body:
                block = next(
                    (n for n in body.named_children() if n.kind() == "block"), None
                )
                statements = block.named_children() if block else body.named_children()
                item["statements"] = [
                    {
                        **location(n),
                        "kind": n.kind(),
                        "text": n.text()[:1600],
                        "truncated": len(n.text()) > 1600,
                    }
                    for n in statements
                ]
                if body.text().lstrip().startswith(("=>", "async =>")):
                    item["returns"].append(
                        {**location(body), "text": body.text()[:1200]}
                    )
            functions.append(item)
        unique_ids(functions)
        types = []
        for node in [*class_nodes, *root.find_all(kind="type_alias")]:
            ident = node.field("name") or next(
                (n for n in node.named_children() if n.kind() == "type_identifier"),
                None,
            )
            if not ident:
                continue
            name = ident.text()
            if node.kind() == "type_alias":
                shape = node.text()
            else:
                body = node.field("body")
                pieces = [node.text().split("{", 1)[0]]
                for child in body.named_children() if body else []:
                    member = next(
                        (
                            n
                            for n in child.named_children()
                            if n.kind() in DECLARATIONS | {"declaration"}
                        ),
                        child,
                    )
                    signature = direct_signature(member)
                    pieces.append(signature.text() + ";" if signature else child.text())
                shape = "\n".join(pieces)
            types.append(
                {
                    "id": file + "::type::" + name,
                    "name": name,
                    "qualified": name,
                    "file": file,
                    **location(node),
                    "kind": node.kind(),
                    "hash": digest(shape.encode()),
                    "text": shape[:8000],
                    "language": "dart",
                }
            )
        return {"functions": functions, "types": types, "parse_error": malformed}

    @staticmethod
    def resolve_call(call, caller, functions):
        found = [
            f
            for f in functions
            if f["name"] == call.get("lookup_name", call["short_name"])
        ]
        receiver = call.get("receiver")
        name = call["short_name"]
        if (
            (receiver or name) in caller["assigned_names"]
            or not receiver
            and name in caller["parameter_names"]
        ):
            return resolution(
                basis="unresolved_receiver",
                reason="binding_may_be_shadowed_or_callable",
            )
        if not receiver and name in caller["field_names"]:
            return resolution(
                basis="unresolved_callable",
                reason="callable_field_requires_type_resolution",
            )
        hints = caller["parameter_types"]
        if receiver == "super":
            return resolution(
                basis="unresolved_receiver", reason="super_requires_type_hierarchy"
            )
        if receiver == "this":
            return resolution(
                [
                    f
                    for f in found
                    if caller["impl"]
                    and f["impl"] == caller["impl"]
                    and f["file"] == caller["file"]
                ],
                "this_owner",
            )
        if receiver in hints:
            hint = nominal(hints[receiver].rstrip("?"))
            if not hint or hint in caller["generic_parameters"]:
                return resolution(
                    basis="unresolved_receiver",
                    reason="unknown_or_polymorphic_receiver",
                )
            owner = hint
            found = [f for f in found if f.get("impl") == owner]
        elif receiver in caller["local_classes"]:
            found = [
                f
                for f in found
                if f.get("impl") == receiver and (f["static"] or f["constructor"])
            ]
        elif receiver:
            if receiver in caller["parameter_names"]:
                return resolution(
                    basis="unresolved_receiver", reason="unknown_receiver_type"
                )
            imported = [
                entry
                for entry in caller["imports"]
                if entry["alias"] == receiver
                and not entry["conditional"]
                and import_allows(entry, name)
                and not name.startswith("_")
            ]
            return resolution(
                [
                    f
                    for f in found
                    if any(f["file"] == entry["file"] for entry in imported)
                    and not f["impl"]
                ],
                "explicit_import",
                None if imported else "unknown_receiver_type",
            )
        if not receiver:
            constructors = [
                f
                for f in found
                if f["constructor"]
                and f["file"] == caller["file"]
                and name in caller["local_classes"]
            ]
            if constructors:
                return resolution(constructors, "local_constructor")
            path = caller["qualified"].split("::")
            for i in range(len(path), -1, -1):
                qualified = "::".join(path[:i] + [name])
                local = [
                    f
                    for f in found
                    if f["file"] == caller["file"]
                    and f["qualified"] == qualified
                    and (
                        not caller["static"]
                        or not f["impl"]
                        or f["static"]
                        or f["constructor"]
                    )
                ]
                if local:
                    return resolution(local)
        same_library = [
            f
            for f in found
            if (f["file"] == caller["file"] or f["file"] in caller["parts"])
            and (receiver or not f["impl"])
        ]
        if same_library:
            return resolution(
                same_library,
                "annotated_parameter_type" if receiver in hints else "local_library",
            )
        imports = [
            entry
            for entry in caller["imports"]
            if not entry["alias"]
            and not entry["conditional"]
            and import_allows(
                entry, nominal(hints.get(receiver, "").rstrip("?")) or name
            )
        ]
        return resolution(
            [
                f
                for f in found
                if any(f["file"] == entry["file"] for entry in imports)
                and not f["name"].startswith("_")
                and (receiver or not f["impl"])
            ],
            "explicit_import",
        )

    @staticmethod
    def related_types(selected, index):
        result = {}
        types = [t for data in index["files"].values() for t in data["types"]]
        for function in selected:
            names = type_names(function)
            visible = {
                function["file"],
                *function["parts"],
                *(
                    entry["file"]
                    for entry in function["imports"]
                    if not entry["conditional"]
                ),
            }
            for item in types:
                if item["name"] in names and item["file"] in visible:
                    result[item["id"]] = item
        return list(result.values())
