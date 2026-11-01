"""Portable source provenance, checked at capture time and verifiable without a checkout.

Integrity hashes detect accidental mixing; they are not signatures or runtime proof.
Full files stay in local facts, never in the default model packet.
"""

from contextlib import contextmanager
from pathlib import Path, PurePosixPath
import subprocess
import tempfile

from . import __version__
from .storage import digest, resolve_source


def git(repo, *args, required=True, input_data=None):
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args], input=input_data, capture_output=True, timeout=60
        )
    except (OSError, subprocess.TimeoutExpired):
        if required:
            raise ValueError("Git source inspection could not complete") from None
        return None
    if result.returncode:
        if required:
            raise ValueError("Git source inspection failed; check repository/ref")
        return None
    return result.stdout


def git_location(repo):
    raw = git(repo, "rev-parse", "--show-toplevel", required=False)
    if raw is None:
        return None
    top = Path(raw.decode().strip()).resolve()
    prefix = Path(repo).resolve().relative_to(top).as_posix()
    return top, "" if prefix == "." else prefix


@contextmanager
def commit_checkout(repo, ref):
    """Read git objects into a temporary tree; never checkout/stash the user's files."""
    location = git_location(repo)
    if not location:
        raise ValueError("--source-ref requires a Git repository")
    top, prefix = location
    commit = git(top, "rev-parse", "--verify", "--end-of-options", ref + "^{commit}").decode().strip()
    entries = []
    for entry in git(top, "ls-tree", "-rz", commit, "--", prefix or ".").split(b"\0"):
        if not entry:
            continue
        meta, path = entry.split(b"\t", 1)
        mode, kind, sha = meta.split()
        if kind == b"blob" and mode in {b"100644", b"100755"}:
            entries.append((path.decode("utf-8"), sha))
    raw = git(top, "cat-file", "--batch", input_data=b"".join(sha + b"\n" for _, sha in entries))
    with tempfile.TemporaryDirectory(prefix="reviewkit-source-") as folder:
        root = Path(folder).resolve()
        offset = 0
        for path, sha in entries:
            end = raw.index(b"\n", offset)
            object_sha, kind, size = raw[offset:end].split()
            if object_sha != sha or kind != b"blob":
                raise ValueError("Unexpected Git object")
            offset = end + 1
            content = raw[offset:offset + int(size)]
            offset += int(size) + 1
            name = PurePosixPath(path)
            if name.is_absolute() or ".." in name.parts or "\\" in path:
                raise ValueError("Unsafe Git source path")
            target = resolve_source(root, path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        # Raw blobs avoid checkout filters, hooks, autocrlf and export substitutions.
        (root / prefix).mkdir(parents=True, exist_ok=True)
        yield root / prefix, {"repository": str(Path(repo).resolve()), "commit": commit, "subdir": prefix}


def capture_source(facts, repo, origin=None, adapter=None):
    repo = Path(repo).resolve()
    location = git_location(origin["repository"] if origin else repo)
    commit = origin["commit"] if origin else None
    dirty = None
    if location:
        top, prefix = location
        if not origin:
            head = git(top, "rev-parse", "HEAD", required=False)
            commit = head.decode().strip() if head else None
            dirty = bool(git(top, "status", "--porcelain", "--untracked-files=normal"))
    else:
        prefix = ""
    files = {}
    verified = bool(commit)
    for name, expected in sorted(facts.get("source_files", {}).items()):
        raw = resolve_source(repo, name).read_bytes()
        if digest(raw) != expected:
            raise ValueError("Source changed during extraction: " + name)
        files[name] = {"sha256": expected, "bom": raw.startswith(b"\xef\xbb\xbf"), "text": raw.decode("utf-8-sig")}
        if commit:
            blob = git(top, "show", f"{commit}:{prefix + '/' if prefix else ''}{name}", required=False)
            verified = verified and blob == raw
    if origin and not verified:
        raise ValueError("Extracted source does not match the requested Git commit")
    body = {
        "schema_version": 1,
        "mode": "git_commit" if verified and (origin or dirty is False) else "workspace",
        "commit": commit,
        "subdir": prefix,
        "worktree_dirty": False if origin else dirty,
        "git_files_verified": verified,
        "tool_version": __version__,
        "adapter": adapter,
        "selection": facts.get("limits", {}),
        "files": files,
    }
    facts["source_snapshot"] = {**body, "id": digest(body)}
    verify_source(facts)
    return facts["source_snapshot"]


def verify_source(facts):
    snapshot = facts.get("source_snapshot")
    if not snapshot:
        return None
    if snapshot.get("id") != digest({k: v for k, v in snapshot.items() if k != "id"}):
        raise ValueError("Source snapshot identity mismatch")
    files = snapshot["files"]
    for name, item in files.items():
        raw = (b"\xef\xbb\xbf" if item.get("bom") else b"") + item["text"].encode("utf-8")
        if digest(raw) != item["sha256"] or facts["source_files"].get(name) != item["sha256"]:
            raise ValueError("Source snapshot file mismatch: " + name)
    if set(files) != set(facts["source_files"]):
        raise ValueError("Source snapshot file selection mismatch")
    for node in [*facts["functions"], *facts.get("types", [])]:
        refs = [node, *node.get("sources", [])]
        for ref in refs:
            text = ref.get("source", ref.get("snippet"))
            if text is None:
                continue
            first, last = ref["line"], ref["end_line"]
            lines = files[ref["file"]]["text"].splitlines()
            if not 1 <= first <= last <= len(lines) or text != "\n".join(lines[first - 1:last]):
                raise ValueError("Node does not match source snapshot: " + ref["file"])
    return snapshot["id"]
