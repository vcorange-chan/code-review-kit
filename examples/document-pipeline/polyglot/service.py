"""Fictional text normalization, used as static review evidence only."""


def normalize_document(value: str) -> str:
    if not value:
        raise ValueError("empty document")
    try:
        return value.encode("ascii").decode("ascii")
    except UnicodeError:
        return value
