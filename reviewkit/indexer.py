from pathlib import Path
import os
import shutil
import subprocess
import time
from .storage import digest, read_json, write_json, resolve_source


def source_files(repo, suffixes):
    rg = shutil.which("rg")
    if rg:
        command = [
            rg,
            "--files",
            "--hidden",
            "-g",
            "!.git",
            "-g",
            "!target",
            "-g",
            "!.deps",
            "-g",
            "!node_modules",
        ]
        for suffix in suffixes:
            command.extend(["-g", "*" + suffix])
        result = subprocess.run(
            command, cwd=repo, capture_output=True, text=True, encoding="utf-8", timeout=60
        )
        if result.returncode not in {0, 1}:
            raise ValueError("rg 文件索引失败: " + result.stderr[:500])
        files = [p.replace("\\", "/") for p in result.stdout.splitlines()]
        return sorted(files), "rg"
    files = []
    for root, dirs, names in os.walk(repo):
        dirs[:] = [
            d
            for d in dirs
            if d not in {".git", "target", ".deps", "node_modules", ".venv", "build"}
        ]
        for name in names:
            if Path(name).suffix in suffixes:
                files.append((Path(root) / name).relative_to(repo).as_posix())
    return sorted(files), "python-walk"


def build_index(repo, adapter, cache_root, refresh=False):
    started = time.perf_counter()
    key = digest(str(repo).encode())[:20]
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
