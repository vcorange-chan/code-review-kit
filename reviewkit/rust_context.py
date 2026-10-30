"""Rust-specific lexical context and conservative receiver hints."""

import re
from .storage import digest


def node_key(node):
    return (node.kind(), node.range().start.index)


def attached_attributes(node):
    result = []
    previous = node.prev()
    while previous:
        if previous.kind() == "attribute_item":
            result.append(previous.text())
        elif previous.kind() not in {"line_comment", "block_comment"}:
            break
        previous = previous.prev()
    return list(reversed(result))


def context_catalog(root):
    return {
        kind: root.find_all(kind=kind)
        for kind in ["inner_attribute_item", "use_declaration", "macro_definition"]
    }


def lexical_context(fn, catalog):
    ancestors = [fn, *fn.ancestors()]
    keys = {node_key(n) for n in ancestors}

    def visible(node):
        if node_key(node.parent()) in keys:
            return True
        owner = next((a for a in node.ancestors() if a.kind() == "function_item"), None)
        return owner is not None and node_key(owner) == node_key(fn)

    attributes = []
    for owner in reversed(ancestors):
        if owner.kind() in {"function_item", "impl_item", "mod_item", "trait_item"}:
            attributes.extend(attached_attributes(owner))
    attributes.extend(n.text() for n in catalog["inner_attribute_item"] if visible(n))
    # Imports can make extension methods available without an explicit trait name.
    imports = [
        {"declaration": n.text(), "attributes": attached_attributes(n)}
        for n in catalog["use_declaration"]
        if visible(n)
    ]
    macros = {
        n.field("name").text(): "\n".join(attached_attributes(n) + [n.text()])
        for n in catalog["macro_definition"]
        if n.field("name") and visible(n)
    }
    pending = set(re.findall(r"\b([A-Za-z_]\w*)\s*!", fn.text()))
    used = {}
    while pending:
        name = pending.pop()
        if name not in macros or name in used:
            continue
        used[name] = macros[name]
        pending.update(re.findall(r"\b([A-Za-z_]\w*)\s*!", macros[name]))
    return digest({"attributes": attributes, "imports": imports, "macros": used})


def parameter_hints(fn):
    generics = set()
    for owner in [fn, *fn.ancestors()]:
        if owner.kind() not in {"function_item", "impl_item", "trait_item"}:
            continue
        generic = owner.field("type_parameters")
        if not generic:
            continue
        for n in generic.find_all(kind="type_parameter"):
            name = n.field("name")
            if name:
                generics.add(name.text())
    hints = {}
    for parameter in fn.field("parameters").named_children():
        pattern = parameter.field("pattern")
        ty = parameter.field("type")
        if not pattern or not ty:
            continue
        name = pattern.text().removeprefix("mut ").strip()
        if re.fullmatch(r"[A-Za-z_]\w*", name):
            hints[name] = {"type": ty.text(), "generic_parameters": sorted(generics)}
    return hints


def shadow_bindings(fn):
    bindings = []
    for kind in [
        "let_declaration",
        "let_condition",
        "for_expression",
        "match_pattern",
        "closure_parameters",
    ]:
        for n in fn.field("body").find_all(kind=kind):
            owner = next((a for a in n.ancestors() if a.kind() == "function_item"), None)
            if owner is not None and node_key(owner) != node_key(fn):
                continue
            pattern = n.field("pattern")
            if not pattern and kind in {"match_pattern", "closure_parameters"}:
                pattern = n
            if pattern:
                bindings.append(
                    (n.range().start.index, set(re.findall(r"\b[A-Za-z_]\w*\b", pattern.text())))
                )
    return bindings


def nominal_path(text):
    text = re.sub(r"^&\s*(?:'[A-Za-z_]\w*\s+)?(?:mut\s+)?", "", text.strip())
    if text.startswith(("dyn ", "impl ")):
        return None
    while True:
        wrapper = re.fullmatch(r"(?:[A-Za-z_]\w*::)*(?:Box|Arc|Rc)\s*<(.+)>", text)
        if not wrapper:
            break
        text = wrapper.group(1).strip()
        if text.startswith(("dyn ", "impl ")):
            return None
    match = re.match(r"(?:[A-Za-z_]\w*::)*[A-Za-z_]\w*", text)
    return match.group(0) if match else None


def nominal_type(text):
    path = nominal_path(text)
    return path.split("::")[-1] if path else None


def owner_path(function):
    path = nominal_path(function.get("impl") or "")
    if not path:
        return None
    if path.startswith("crate::"):
        return path.removeprefix("crate::")
    return "::".join([*function.get("module_path", []), path])


def parameter_owner(type_text, caller):
    path = nominal_path(type_text)
    if path is None:
        return None
    module = caller.get("module_path", [])
    if "::" not in path:
        return "::".join([*module, path])
    if path.startswith("crate::"):
        return path.removeprefix("crate::")
    if path.startswith("self::"):
        return "::".join([*module, path.removeprefix("self::")])
    if path.startswith("super::") and module:
        return "::".join([*module[:-1], path.removeprefix("super::")])
    return None
