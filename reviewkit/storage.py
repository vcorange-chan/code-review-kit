from pathlib import Path
import hashlib
import json
import os


def digest(value):
    raw = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True, ensure_ascii=False).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write_json(path, value, compact=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f'.{os.getpid()}.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=None if compact else 2,
                               separators=(',',':') if compact else None), encoding='utf-8')
    os.replace(temp, path)


def resolve_source(repo, relative):
    """Evidence paths cannot escape the read-only repository root."""
    result = (repo / relative).resolve()
    if not result.is_relative_to(repo.resolve()):
        raise ValueError(f'源码路径超出仓库: {relative}')
    return result
