"""Shared syntax-tree traversal; language-specific node kinds live in adapters."""

SITE_VERSION = 1


def tree_sites(text, language, kinds):
    from ast_grep_py import SgRoot
    from .syntax_support import node_location

    pending = [SgRoot(text, language).root()]
    result = []
    while pending:
        node = pending.pop()
        kind = kinds.get(node.kind())
        if kind:
            result.append({**node_location(node), "kind": kind, "text": node.text()})
        pending.extend(reversed(node.named_children()))
    return result
