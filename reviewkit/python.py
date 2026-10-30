"""Python AST facts. Parsing never imports or executes the reviewed repository."""

import ast
import re
import sys
from functools import lru_cache
from pathlib import PurePosixPath
from .storage import digest
from .syntax_support import function_record, nominal, resolution, type_names, unique_ids

FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)
SCOPES = (*FUNCTIONS, ast.ClassDef, ast.Lambda)


def module_name(file):
    parts = list(PurePosixPath(file).with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def imports_in(statements, file):
    result = {}

    def bind(name, value, statement):
        conditional = not isinstance(statement, (ast.Import, ast.ImportFrom))
        if conditional:
            value["conditional_context"] = ast.dump(statement, include_attributes=False)
        if name in result and result[name] != value:
            value["multiple_bindings"] = True
        result[name] = value

    for statement in statements:
        # Imports in conditional blocks are candidates, not proven executed bindings.
        for node in owned(statement, include_root=True):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    local = alias.asname or alias.name.split(".")[0]
                    bind(
                        local,
                        {
                            "module": alias.name if alias.asname else local,
                            "symbol": None,
                        },
                        statement,
                    )
            elif isinstance(node, ast.ImportFrom):
                prefix = node.module or ""
                if node.level:
                    parts = list(PurePosixPath(file).parent.parts)
                    up = node.level - 1
                    parts = parts[: len(parts) - up] if up <= len(parts) else []
                    prefix = ".".join(parts + ([prefix] if prefix else []))
                for alias in node.names:
                    bind(
                        alias.asname or alias.name,
                        {
                            "module": prefix,
                            "symbol": alias.name,
                        },
                        statement,
                    )
    return result


def owned(node, include_root=False):
    if isinstance(node, SCOPES):
        return
    if include_root:
        yield node
    for child in ast.iter_child_nodes(node):
        yield from owned(child, True)


def body_nodes(function):
    return [node for statement in function.body for node in owned(statement, True)]


def assigned_names(nodes):
    return {
        node.id
        for node in nodes
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del))
    }


class PythonAdapter:
    language = "python"
    suffixes = (".py", ".pyi")
    version = "python-ast-1:" + ".".join(map(str, sys.version_info[:2]))
    sample = "def probe():\n    return 1\n"

    def parse(self, text, file):
        try:
            tree = ast.parse(text, filename=file, type_comments=True)
        except SyntaxError as error:
            return {
                "functions": [],
                "types": [],
                "parse_error": True,
                "diagnostics": [{"line": error.lineno, "message": error.msg}],
            }
        lines = text.splitlines(keepends=True)

        @lru_cache(maxsize=None)
        def snippet(node):
            return ast.get_source_segment(text, node) or ast.unparse(node)

        def loc(node):
            return {"line": node.lineno, "end_line": node.end_lineno or node.lineno}

        def header(node):
            first = node.body[0]
            prefix = "".join(lines[node.lineno - 1 : first.lineno])
            # AST columns are UTF-8 bytes, including non-ASCII identifiers.
            prefix = prefix.encode("utf-8")
            prefix = prefix[
                : len(prefix)
                - len(lines[first.lineno - 1].encode("utf-8"))
                + first.col_offset
            ]
            return prefix.decode("utf-8").strip().rstrip(":").strip()

        parents = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent

        def scopes(node):
            result = []
            parent = parents.get(node)
            while parent is not None:
                if isinstance(parent, (*FUNCTIONS, ast.ClassDef)):
                    result.append(parent)
                parent = parents.get(parent)
            return list(reversed(result))

        module_imports = imports_in(tree.body, file)
        globals_used = {
            name: snippet(statement)
            for statement in tree.body
            if isinstance(statement, (ast.Assign, ast.AnnAssign))
            for name in assigned_names(owned(statement, True))
        }
        classes = {
            node.name: node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        }
        functions = []
        for fn in [node for node in ast.walk(tree) if isinstance(node, FUNCTIONS)]:
            ancestors = scopes(fn)
            qualified = "::".join([n.name for n in ancestors] + [fn.name])
            owner = (
                ancestors[-1]
                if ancestors and isinstance(ancestors[-1], ast.ClassDef)
                else None
            )
            nodes = body_nodes(fn)
            signature_nodes = [
                *ast.walk(fn.args),
                *(n for d in fn.decorator_list for n in ast.walk(d)),
            ]
            if fn.returns:
                signature_nodes.extend(ast.walk(fn.returns))
            names = {
                n.id for n in [*nodes, *signature_nodes] if isinstance(n, ast.Name)
            }
            context = {
                "imports": module_imports,
                "ancestors": [
                    {
                        "header": header(n),
                        "decorators": [snippet(d) for d in n.decorator_list],
                    }
                    for n in ancestors
                ],
                "globals": {
                    key: value for key, value in globals_used.items() if key in names
                },
            }
            start = min([fn.lineno] + [d.lineno for d in fn.decorator_list])
            source = "".join(lines[start - 1 : fn.end_lineno]).rstrip("\r\n")
            item = function_record(
                file, qualified, start, fn.end_lineno, source, context
            )
            imports = dict(module_imports)
            for scope in [*ancestors, fn]:
                if isinstance(scope, FUNCTIONS):
                    imports.update(imports_in(scope.body, file))
            parameters = [*fn.args.posonlyargs, *fn.args.args, *fn.args.kwonlyargs]
            if fn.args.vararg:
                parameters.append(fn.args.vararg)
            if fn.args.kwarg:
                parameters.append(fn.args.kwarg)
            decorators = [snippet(d) for d in fn.decorator_list]
            bound = (
                parameters[0].arg
                if owner and parameters and "staticmethod" not in decorators
                else None
            )
            item.update(
                {
                    "language": "python",
                    "signature": header(fn),
                    "parameters": "(" + ast.unparse(fn.args) + ")",
                    "return_type": snippet(fn.returns) if fn.returns else "unspecified",
                    "impl": "::".join(n.name for n in ancestors) if owner else None,
                    "bound_receiver": bound,
                    "parameter_names": [a.arg for a in parameters],
                    "parameter_types": {
                        a.arg: snippet(a.annotation) for a in parameters if a.annotation
                    },
                    "imports": imports,
                    "module": module_name(file),
                    "shadowed_imports": sorted(set(globals_used) & set(module_imports)),
                    "lexical_scopes": [
                        qualified,
                        *(
                            "::".join(n.name for n in ancestors[: i + 1])
                            for i, a in reversed(list(enumerate(ancestors)))
                            if isinstance(a, FUNCTIONS)
                        ),
                        "",
                    ],
                    "local_classes": sorted(classes),
                    "assigned_names": sorted(assigned_names(nodes)),
                    "async": isinstance(fn, ast.AsyncFunctionDef),
                    "test": fn.name.startswith("test_")
                    or PurePosixPath(file).name.startswith("test_"),
                    "decorators": decorators,
                    "referenced_types": sorted(names),
                    "analysis_limits": [
                        "dynamic_dispatch_and_decorators_not_resolved",
                        "implicit_exceptions_not_enumerated",
                    ],
                }
            )
            for n in sorted(
                nodes,
                key=lambda n: (getattr(n, "lineno", 0), getattr(n, "col_offset", 0)),
            ):
                if isinstance(n, ast.Call):
                    callee = n.func
                    receiver = (
                        snippet(callee.value)
                        if isinstance(callee, ast.Attribute)
                        else None
                    )
                    name = (
                        callee.attr
                        if isinstance(callee, ast.Attribute)
                        else snippet(callee)
                    )
                    binding = imports.get(name) if not receiver else None
                    item["calls"].append(
                        {
                            **loc(n),
                            "name": snippet(callee),
                            "short_name": name,
                            "lookup_name": (
                                binding["symbol"]
                                if binding and binding["symbol"]
                                else name
                            ),
                            "receiver": receiver,
                            "expression": snippet(n)[:500],
                            "truncated": len(snippet(n)) > 500,
                        }
                    )
                if isinstance(
                    n, (ast.If, ast.IfExp, ast.For, ast.AsyncFor, ast.While, ast.Match)
                ):
                    condition = (
                        getattr(n, "test", None)
                        or getattr(n, "iter", None)
                        or getattr(n, "subject", None)
                    )
                    arms = (
                        [
                            ast.unparse(c.pattern)
                            + (" if " + ast.unparse(c.guard) if c.guard else "")
                            for c in n.cases
                        ]
                        if isinstance(n, ast.Match)
                        else []
                    )
                    item["branches"].append(
                        {
                            **loc(n),
                            "kind": type(n).__name__,
                            "condition": snippet(condition)[:800] if condition else "",
                            "has_else": bool(getattr(n, "orelse", [])),
                            "arms": arms,
                        }
                    )
                if isinstance(n, (ast.Try, ast.TryStar)):
                    item["tries"].append({**loc(n), "text": snippet(n)[:1600]})
                    item["branches"].append(
                        {
                            **loc(n),
                            "kind": type(n).__name__,
                            "condition": "exception handling",
                            "has_else": bool(n.orelse),
                            "arms": [
                                (
                                    snippet(h.type)
                                    if h.type
                                    else "BaseException (bare except)"
                                )
                                for h in n.handlers
                            ]
                            + (["finally"] if n.finalbody else []),
                        }
                    )
                if isinstance(n, ast.Await):
                    item["tries"].append({**loc(n), "text": snippet(n)[:1200]})
                if isinstance(n, ast.Return):
                    item["returns"].append({**loc(n), "text": snippet(n)[:1200]})
                if isinstance(n, (ast.Raise, ast.Assert)):
                    value = n.exc if isinstance(n, ast.Raise) else n.test
                    item["errors"].append(
                        {
                            **loc(n),
                            "variant": snippet(value) if value else "re-raise",
                            "expression": snippet(n)[:1200],
                        }
                    )
            item["statements"] = [
                {
                    **loc(n),
                    "kind": type(n).__name__,
                    "text": snippet(n)[:1600],
                    "truncated": len(snippet(n)) > 1600,
                }
                for n in fn.body
            ]
            functions.append(item)
        unique_ids(functions)
        types = []
        for node in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
            qualified = "::".join([n.name for n in scopes(node)] + [node.name])
            shape = "\n".join(
                [*("@" + snippet(d) for d in node.decorator_list), header(node)]
                + [
                    header(n) + ": ..." if isinstance(n, FUNCTIONS) else snippet(n)
                    for n in node.body
                    if not isinstance(n, ast.ClassDef)
                ]
            )
            types.append(
                {
                    "id": file + "::type::" + qualified,
                    "name": node.name,
                    "qualified": qualified,
                    "file": file,
                    **loc(node),
                    "kind": "class",
                    "hash": digest(shape.encode()),
                    "text": shape[:8000],
                    "language": "python",
                }
            )
        return {"functions": functions, "types": types, "parse_error": False}

    @staticmethod
    def resolve_call(call, caller, functions):
        found = [
            f
            for f in functions
            if f["name"] == call.get("lookup_name", call["short_name"])
        ]
        receiver = call.get("receiver")
        raw_name = call["name"].split(".")[0]
        assigned = set(caller["assigned_names"])
        imports = caller["imports"]
        if raw_name in caller["shadowed_imports"]:
            return resolution(
                basis="unresolved_callable", reason="import_binding_may_be_rebound"
            )
        binding = imports.get(raw_name, {})
        if binding.get("conditional_context") or binding.get("multiple_bindings"):
            return resolution(
                basis="unresolved_import",
                reason="conditional_or_multiple_import_bindings",
            )

        def imported(binding, owner=None):
            if binding.get("conditional_context") or binding.get("multiple_bindings"):
                return []
            return [
                f
                for f in found
                if f.get("module") == binding["module"] and f.get("impl") == owner
            ]

        if receiver:
            if receiver in assigned:
                return resolution(
                    basis="unresolved_receiver",
                    reason="receiver_binding_may_be_shadowed",
                )
            if receiver == caller.get("bound_receiver"):
                return resolution(
                    [
                        f
                        for f in found
                        if f["file"] == caller["file"]
                        and f.get("impl") == caller["impl"]
                    ],
                    "bound_receiver",
                )
            hint = nominal(caller.get("parameter_types", {}).get(receiver, ""))
            if hint:
                binding = imports.get(hint)
                if binding and binding["symbol"]:
                    return resolution(
                        imported(binding, binding["symbol"]), "annotated_parameter_type"
                    )
                if hint in caller["local_classes"]:
                    return resolution(
                        [
                            f
                            for f in found
                            if f["file"] == caller["file"] and f.get("impl") == hint
                        ],
                        "annotated_parameter_type",
                    )
            if receiver in caller["parameter_names"]:
                return resolution(
                    basis="unresolved_receiver",
                    reason="unknown_or_polymorphic_receiver",
                )
            binding = imports.get(receiver)
            if binding:
                return resolution(
                    imported(binding, binding["symbol"]), "explicit_import"
                )
            if receiver in caller["local_classes"]:
                return resolution(
                    [
                        f
                        for f in found
                        if f["file"] == caller["file"] and f.get("impl") == receiver
                    ],
                    "nominal_owner",
                )
            return resolution(
                basis="unresolved_receiver", reason="unknown_or_polymorphic_receiver"
            )
        if raw_name in caller["parameter_names"] or raw_name in assigned:
            return resolution(
                basis="unresolved_callable", reason="callable_parameter_or_rebound_name"
            )
        if raw_name in imports:
            return resolution(imported(imports[raw_name]), "explicit_import")
        # Class bodies are not enclosing lexical function scopes in Python.
        for scope in caller["lexical_scopes"]:
            target = (scope + "::" if scope else "") + call["short_name"]
            candidates = [
                f
                for f in found
                if f["file"] == caller["file"] and f["qualified"] == target
            ]
            if candidates:
                return resolution(candidates)
        return resolution()

    @staticmethod
    def related_types(selected, index):
        result = {}
        types = [t for data in index["files"].values() for t in data["types"]]
        for function in selected:
            names = type_names(function)
            imported_types = {
                (binding["module"], binding["symbol"])
                for name, binding in function["imports"].items()
                if name in names and binding["symbol"]
            }
            for item in types:
                if (item["name"] in names and item["file"] == function["file"]) or (
                    module_name(item["file"]),
                    item["name"],
                ) in imported_types:
                    result[item["id"]] = item
        return list(result.values())
