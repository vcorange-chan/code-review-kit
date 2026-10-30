from pathlib import Path
from .storage import digest, read_json


def build_key(args, index, manifest, notes, home):
    code = {
        p.relative_to(home).as_posix(): digest(p.read_bytes())
        for p in (home / "reviewkit").rglob("*")
        if p.is_file() and (p.suffix == ".py" or "templates" in p.parts)
    }
    return digest(
        {
            "repository": index["repository"],
            "adapter": index["adapter"],
            "code": code,
            "command": args.command,
            "manifest": manifest,
            "symbol": getattr(args, "symbol", None),
            "file": getattr(args, "file", None),
            "title": getattr(args, "title", None),
            "link_mode": getattr(args, "link_mode", "embedded"),
            "link_template": getattr(args, "link_template", None),
            "depth": args.depth,
            "max_nodes": args.max_nodes,
            "packet_bytes": args.packet_bytes,
            "notes": notes,
        }
    )


def can_reuse(out, key, index):
    if not all(
        (out / name).exists()
        for name in [
            "index.html",
            "facts.json",
            "evidence-packet.json",
            "explanations.seed.json",
            "build-state.json",
            "build-stats.json",
        ]
    ):
        return False
    state = read_json(out / "build-state.json")
    if state.get("key") != key:
        return False
    if index["stats"]["parsed_files"] or index["stats"]["removed_files"]:
        return False
    repo = Path(index["repository"])
    for name, expected in state["source_files"].items():
        data = index["files"].get(name)
        if data:
            if data["file_hash"] != expected:
                return False
        else:
            path = repo / name
            if not path.is_file() or digest(path.read_bytes()) != expected:
                return False
    return True
