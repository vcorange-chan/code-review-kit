"""Shared adapter contract. Only Rust is registered."""

from typing import Protocol
from .rust import RustAdapter


class LanguageAdapter(Protocol):
    language: str
    suffixes: tuple[str, ...]
    version: str

    def parse(self, text, file): ...
    def resolve_call(self, call, caller, functions): ...
    def related_types(self, selected, index): ...


ADAPTERS = {"rust": RustAdapter}


def adapter_for(language):
    if language not in ADAPTERS:
        raise ValueError(f"当前未实现 {language!r} 自动分析；可用语言：" + ", ".join(ADAPTERS))
    return ADAPTERS[language]()
