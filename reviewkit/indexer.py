from pathlib import Path
import os
import shutil
import subprocess
import time
from .storage import digest, read_json, write_json, resolve_source
from .file_selection import EXCLUDED_DIRS, FileSelection


def source_files(repo, suffixes):
    repo = Path(repo).resolve()
    policy = FileSelection(repo, suffixes)
    rg = shutil.which("rg")
    if rg:
        # rg supplies candidates, not a second set of ignore semantics.
        command = [rg, "--files", "--hidden", "--no-ignore", "--no-config", "--null"]
        for directory in sorted(EXCLUDED_DIRS):
            command.extend(["-g", "!" + directory])
        for suffix in suffixes:
            command.extend(["-g", "*" + suffix])
        result = subprocess.run(
            command,
            cwd=repo,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
        if result.returncode not in {0, 1}:
            raise ValueError("rg 文件索引失败: " + result.stderr[:500])
        candidates = [Path(p).as_posix() for p in result.stdout.split("\0") if p]
        files = [name for name in candidates if policy.allows_file(name)]
        return sorted(files), "rg"
    files = []

    def on_error(error):
        raise error

    for root, dirs, names in os.walk(repo, onerror=on_error, followlinks=False):
        dirs[:] = [
            d
            for d in dirs
            if policy.allows_directory((Path(root) / d).relative_to(repo).as_posix())
        ]
        for name in names:
            relative = (Path(root) / name).relative_to(repo).as_posix()
            if policy.allows_file(relative):
                files.append(relative)
    return sorted(files), "python-walk"


def build_index(repo, adapter, cache_root, refresh=False):
    started = time.perf_counter()
    key = digest((str(repo) + "\0" + adapter.language).encode())[:20]
    cache_path = cache_root / (key + ".json")
    previous = read_json(cache_path) if cache_path.exists() and not refresh else {}
    if previous.get("adapter") != adapter.version:
        previous = {}
    names, finder = source_files(repo, adapter.suffixes)
    old = previous.get("files", {})
    files = {}
    parsed = reused = 0
    for name in names:
        path = resolve_source(repo, name)
        raw = path.read_bytes()
        file_hash = digest(raw)
        if name in old and old[name]["file_hash"] == file_hash:
            files[name] = old[name]
            reused += 1
        else:
            text = raw.decode("utf-8-sig").replace("\r\n", "\n")
            files[name] = {"file_hash": file_hash, **adapter.parse(text, name)}
            parsed += 1
        data = files[name]
        data.setdefault("language", adapter.language)
        for item in data["functions"] + data["types"]:
            item.setdefault("language", data["language"])
    index = {
        "schema_version": 1,
        "repository": str(repo),
        "language": adapter.language,
        "adapter": adapter.version,
        "files": files,
    }
    write_json(cache_path, index, compact=True)
    index["stats"] = {
        "files": len(files),
        "parsed_files": parsed,
        "reused_files": reused,
        "removed_files": len(set(old) - set(files)),
        "finder": finder,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    return index
