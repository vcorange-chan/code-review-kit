"""Adapter registry and mixed-language routing shared by every entry point."""

from typing import Protocol
from .rust import RustAdapter
from .python import PythonAdapter
from .dart import DartAdapter


class LanguageAdapter(Protocol):
    language: str
    suffixes: tuple[str, ...]
    version: str

    def parse(self, text, file): ...
    def resolve_call(self, call, caller, functions): ...
    def related_types(self, selected, index): ...
    def search_sites(self, text, file): ...


ADAPTERS = {"rust": RustAdapter, "python": PythonAdapter, "dart": DartAdapter}


class AutoAdapter:
    language = "auto"

    def search_sites(self, text, file):
        from pathlib import PurePosixPath

        adapter = next(
            a
            for a in self.adapters.values()
            if PurePosixPath(file).suffix in a.suffixes
        )
        return adapter.search_sites(text, file)

    def __init__(self):
        self.adapters = {name: cls() for name, cls in ADAPTERS.items()}
        self.suffixes = tuple(
            s for adapter in self.adapters.values() for s in adapter.suffixes
        )
        self.version = "mixed-1:" + ":".join(a.version for a in self.adapters.values())

    def parse(self, text, file):
        from pathlib import PurePosixPath

        adapter = next(
            a
            for a in self.adapters.values()
            if PurePosixPath(file).suffix in a.suffixes
        )
        return {"language": adapter.language, **adapter.parse(text, file)}

    def resolve_call(self, call, caller, functions):
        language = caller["language"]
        return self.adapters[language].resolve_call(
            call, caller, [f for f in functions if f["language"] == language]
        )

    def related_types(self, selected, index):
        result = []
        for language, adapter in self.adapters.items():
            subset = [f for f in selected if f["language"] == language]
            if subset:
                view = {
                    **index,
                    "files": {
                        name: data
                        for name, data in index["files"].items()
                        if data["language"] == language
                    },
                }
                result.extend(adapter.related_types(subset, view))
        return result


def adapter_for(language):
    if language == "auto":
        return AutoAdapter()
    if language not in ADAPTERS:
        raise ValueError(
            f"当前未实现 {language!r} 自动分析；可用语言：" + ", ".join(ADAPTERS)
        )
    return ADAPTERS[language]()
