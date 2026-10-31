"""One repository-scoped selection policy for every file enumerator and language."""

import posixpath
from pathlib import Path, PurePosixPath

# Hard exclusions are shared, including generated local reviews and private state.
EXCLUDED_DIRS = frozenset(
    {
        ".git",
        "target",
        ".deps",
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        ".dart_tool",
        "build",
        "out",
        ".local",
        ".cache",
    }
)
IGNORE_FILES = (".gitignore", ".ignore", ".rgignore")


class FileSelection:
    def __init__(self, repo, suffixes):
        self.repo = Path(repo).resolve()
        self.suffixes = tuple(suffixes)
        self._scopes = {}
        self._directories = {"": True}

    def _rules_for(self, directory):
        if directory in self._scopes:
            return self._scopes[directory]
        rules = list(self._rules_for(posixpath.dirname(directory))) if directory else []
        for priority, filename in enumerate(IGNORE_FILES):
            path = self.repo / directory / filename
            if path.is_symlink():
                raise ValueError("Ignore rule file must not be a symlink: " + filename)
            if path.is_file():
                from pathspec import GitIgnoreSpec

                spec = GitIgnoreSpec.from_lines(
                    path.read_text(encoding="utf-8-sig").splitlines(), backend="simple"
                )
                rules.append((directory, priority, spec))
        # File-kind precedence, then deeper rules within each kind.
        rules.sort(key=lambda rule: (rule[1], len(PurePosixPath(rule[0]).parts)))
        self._scopes[directory] = tuple(rules)
        return self._scopes[directory]

    def _ignored(self, name, directory):
        ignored = False
        parent = posixpath.dirname(name)
        for base, _, spec in self._rules_for(parent):
            relative = name[len(base) + 1 :] if base else name
            result = spec.check_file(relative + ("/" if directory else "")).include
            if result is not None:
                ignored = result
        return ignored

    def allows_directory(self, name):
        if name in self._directories:
            return self._directories[name]
        path = PurePosixPath(name)
        allowed = (
            not path.is_absolute()
            and ".." not in path.parts
            and not set(path.parts).intersection(EXCLUDED_DIRS)
            and not (self.repo / name).is_symlink()
            and self.allows_directory(posixpath.dirname(name))
            and not self._ignored(name, directory=True)
        )
        self._directories[name] = allowed
        return allowed

    def allows_file(self, name):
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or path.suffix not in self.suffixes:
            return False
        if not self.allows_directory(posixpath.dirname(name)):
            return False
        source = self.repo / name
        return (
            not source.is_symlink()
            and source.is_file()
            and not self._ignored(name, directory=False)
        )
