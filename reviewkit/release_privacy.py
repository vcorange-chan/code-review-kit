"""Offline publication checks. Diagnostics never print matched private text."""

from pathlib import Path, PurePosixPath
import hashlib
import io
import json
import os
import re
import stat
import subprocess
import tarfile
import tempfile
import unicodedata
import zipfile
import base64
import csv
import configparser
from email.parser import BytesParser

POLICY = ".release-policy.json"
DENIED_PARTS = {".local", "out", ".cache", ".deps", "__pycache__", "node_modules", ".git"}
DENIED_NAMES = {
    "facts.json",
    "evidence-packet.json",
    "build-stats.json",
    "build-state.json",
    "explanations.seed.json",
}
MAX_BYTES = 32 * 1024 * 1024
SKILL_ARCHIVES = {"code-review-kit-skill.zip": "code-review-kit", "copy-tutor-skill.zip": "copy-tutor"}
HOST_PATH = re.compile(r'(?i)(?:\b[a-z]:[/\\](?![\[<{])[^\s"\']+|/(?:Users|home)/[^/\s<>\[{}]+)')


class PrivacyError(ValueError):
    def __init__(self, rule, entry):
        self.rule = rule
        self.entry = entry
        token = hashlib.sha256(str(entry).encode()).hexdigest()[:12]
        super().__init__(f"Publication blocked: {rule}; entry={token}")


def digest(data):
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def file_digest(name, data):
    return hashlib.sha256(data).hexdigest() if name.lower().endswith(".png") else digest(data)


def terms_for(root, require=False):
    terms = []
    local = Path(root) / ".local/privacy-denylist.json"
    configured = local.is_file() or bool(os.environ.get("REVIEW_KIT_PRIVATE_TERMS", ""))

    def add(raw):
        try:
            value = json.loads(raw)
        except ValueError:
            raise PrivacyError("invalid-private-policy", "private-policy")
        if not isinstance(value, list):
            raise PrivacyError("invalid-private-policy", "private-policy")
        terms.extend(value)

    if local.is_file():
        add(local.read_text(encoding="utf-8-sig"))
    raw = os.environ.get("REVIEW_KIT_PRIVATE_TERMS", "")
    if raw:
        add(raw)
    if any(not isinstance(t, str) or not t.strip() for t in terms):
        raise PrivacyError("invalid-private-policy", "private-policy")
    if require and not configured:
        raise PrivacyError("private-policy-required", "private-policy")
    return [
        re.sub("/+", "/", unicodedata.normalize("NFKC", t).replace("\\", "/")).casefold()
        for t in terms
    ]


def check_text(data, entry, terms=(), allow_report=False):
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise PrivacyError("unapproved-binary", entry)
    normalized = unicodedata.normalize("NFKC", text).replace("\\", "/")
    normalized = re.sub("/+", "/", normalized)
    if HOST_PATH.search(normalized):
        raise PrivacyError("host-absolute-path", entry)
    if any(t in normalized.casefold() for t in terms):
        raise PrivacyError("private-term", entry)
    if (
        not allow_report
        and str(entry).endswith(".html")
        and 'class="stage"' in text
        and "data-status=" in text
    ):
        raise PrivacyError("generated-review-html", entry)
    try:
        obj = json.loads(text)
    except (ValueError, TypeError):
        return
    if isinstance(obj, dict) and (
        obj.get("privacy_check_report")
        or {"root_ids", "card_evidence"} <= obj.keys()
        or {"repository", "functions"} <= obj.keys()
        or {"html", "packet", "index"} <= obj.keys()
    ):
        raise PrivacyError("review-or-private-report", entry)


def safe_name(name):
    path = PurePosixPath(name)
    if "\\" in name or path.is_absolute() or ".." in path.parts or ":" in name:
        raise PrivacyError("unsafe-entry-path", name)
    if set(path.parts) & DENIED_PARTS or path.name in DENIED_NAMES:
        raise PrivacyError("private-or-generated-entry", name)
    return path.as_posix()


def read_policy(root):
    value = json.loads((Path(root) / POLICY).read_text(encoding="utf-8-sig"))
    if value.get("schema_version") != 1 or not isinstance(value.get("source_hashes"), dict):
        raise PrivacyError("invalid-release-policy", POLICY)
    for name, expected in value["source_hashes"].items():
        safe_name(name)
        if not re.fullmatch("[a-f0-9]{64}", expected):
            raise PrivacyError("invalid-source-digest", name)
    return value


def check_source_entry(name, data, policy, terms):
    safe_name(name)
    if name != POLICY:
        expected = policy["source_hashes"].get(name)
        if expected is None:
            raise PrivacyError("source-not-allowlisted", name)
        if file_digest(name, data) != expected:
            raise PrivacyError("source-not-reviewed", name)
    if name.lower().endswith(".png"):
        return  # Exact approved digest above; images require human review before approval.
    check_text(data, name, terms)


def source_files(root):
    root = Path(root).resolve()
    try:
        top = (
            subprocess.check_output(
                ["git", "rev-parse", "--show-toplevel"], cwd=root, stderr=subprocess.DEVNULL
            )
            .decode()
            .strip()
        )
        if Path(top).resolve() != root:
            raise ValueError()
        raw = subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=root
        )
        names = set(raw.decode().split("\0")) - {""}
    except (subprocess.CalledProcessError, ValueError, FileNotFoundError):
        names = set(read_policy(root)["source_hashes"]) | {POLICY}
    # Catch ignored files that a broad copytree could accidentally package.
    for folder in ["reviewkit", *("skills/" + skill for skill in SKILL_ARCHIVES.values())]:
        for path in (root / folder).rglob("*"):
            if path.is_symlink():
                raise PrivacyError("source-symlink", path.relative_to(root))
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                names.add(path.relative_to(root).as_posix())
    return names


def check_source(root, require_terms=False):
    root = Path(root).resolve()
    policy = read_policy(root)
    terms = terms_for(root, require_terms)
    names = source_files(root)
    expected = set(policy["source_hashes"]) | {POLICY}
    if expected - names:
        raise PrivacyError("approved-source-missing", sorted(expected - names)[0])
    for name in sorted(names):
        path = root / safe_name(name)
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise PrivacyError("source-symlink", name)
        if path.stat().st_size > MAX_BYTES:
            raise PrivacyError("source-too-large", name)
        check_source_entry(name, path.read_bytes(), policy, terms)
    return {
        "ok": True,
        "source_files": len(names),
        "private_terms_configured": bool(os.environ.get("REVIEW_KIT_PRIVATE_TERMS", ""))
        or (root / ".local/privacy-denylist.json").is_file(),
        "private_terms_count": len(terms),
    }


def skill_mapping(policy, skill="code-review-kit"):
    """Each skill ZIP carries its own folder plus the shared tool, so it installs alone."""
    result = {}
    prefix = f"skills/{skill}/"
    for name in policy["source_hashes"]:
        if name.startswith(prefix):
            result[skill + "/" + name.removeprefix(prefix)] = name
        elif name.startswith("reviewkit/") or name in {"review.py", "requirements.txt"}:
            result[skill + "/scripts/tool/" + name] = name
        elif name == "LICENSE":
            result[skill + "/LICENSE"] = name
    return result


def version_for(root):
    import tomllib

    return tomllib.loads((Path(root) / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "version"
    ]


def check_wheel_metadata(root, entries, version):
    import tomllib

    root = Path(root)
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    prefix = f"code_review_kit-{version}.dist-info/"
    if any(prefix + name not in entries for name in ["METADATA", "WHEEL", "RECORD"]):
        raise PrivacyError("wheel-metadata-incomplete", "wheel")
    metadata = BytesParser().parsebytes(entries[prefix + "METADATA"])
    expected = {
        "Name": project.get("name", "code-review-kit"),
        "Version": version,
        "Summary": project.get("description", ""),
        "Requires-Python": project.get("requires-python", ""),
        "Description-Content-Type": "text/markdown",
    }
    for key, value in expected.items():
        if str(metadata.get(key, "")) != value:
            raise PrivacyError("wheel-metadata-not-approved", key)
    if any(
        metadata.get(key)
        for key in [
            "Author",
            "Author-email",
            "Maintainer",
            "Maintainer-email",
            "Home-page",
            "Download-URL",
            "Project-URL",
        ]
    ):
        raise PrivacyError("wheel-unconfigured-personal-metadata", "wheel")
    body = metadata.get_payload(decode=True) or b""
    if body.replace(b"\r\n", b"\n") != (root / "README.md").read_bytes().replace(b"\r\n", b"\n"):
        raise PrivacyError("wheel-description-not-approved", "METADATA")
    for name, data in entries.items():
        if name.endswith("/licenses/LICENSE") and data != (root / "LICENSE").read_bytes():
            raise PrivacyError("wheel-license-not-approved", "LICENSE")
    entry_file = prefix + "entry_points.txt"
    if entry_file in entries:
        config = configparser.ConfigParser(interpolation=None)
        config.optionxform = str
        config.read_string(entries[entry_file].decode())
        if config.sections() != ["console_scripts"] or dict(
            config["console_scripts"]
        ) != project.get("scripts", {}):
            raise PrivacyError("wheel-entry-points-not-approved", "entry-points")
    rows = list(csv.reader(io.StringIO(entries[prefix + "RECORD"].decode())))
    if (
        len(rows) != len(entries)
        or any(len(row) != 3 for row in rows)
        or {r[0] for r in rows} != set(entries)
    ):
        raise PrivacyError("wheel-record-not-approved", "RECORD")
    for name, checksum, size in rows:
        expected_hash = "sha256=" + base64.urlsafe_b64encode(
            hashlib.sha256(entries[name]).digest()
        ).decode().rstrip("=")
        if name == prefix + "RECORD":
            valid = not checksum and not size
        else:
            valid = checksum == expected_hash and size == str(len(entries[name]))
        if not valid:
            raise PrivacyError("wheel-record-digest-mismatch", "RECORD")


def check_archive(root, asset, terms):
    root = Path(root)
    policy = read_policy(root)
    asset = Path(asset)
    version = version_for(root)
    name = asset.name
    seen = set()
    entries = {}
    total = 0
    if name in SKILL_ARCHIVES:
        mapping = skill_mapping(policy, SKILL_ARCHIVES[name])
        required = set(mapping)
        kind = "skill"
    elif name == f"code_review_kit-{version}-py3-none-any.whl":
        mapping = {n: n for n in policy["source_hashes"] if n.startswith("reviewkit/")}
        required = set(mapping)
        kind = "wheel"
    else:
        raise PrivacyError("unapproved-archive", name)
    with zipfile.ZipFile(asset) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            entry = safe_name(info.filename)
            if entry in seen or stat.S_ISLNK(info.external_attr >> 16):
                raise PrivacyError("duplicate-or-symlink-entry", entry)
            seen.add(entry)
            total += info.file_size
            if total > MAX_BYTES:
                raise PrivacyError("archive-too-large", name)
            data = archive.read(info)
            entries[entry] = data
            if entry in mapping:
                source = mapping[entry]
                if file_digest(source, data) != policy["source_hashes"][source]:
                    raise PrivacyError("archive-source-mismatch", entry)
            elif (
                kind == "wheel"
                and entry.startswith(f"code_review_kit-{version}.dist-info/")
                and entry.split(".dist-info/", 1)[1]
                in {
                    "METADATA",
                    "WHEEL",
                    "RECORD",
                    "entry_points.txt",
                    "top_level.txt",
                    "licenses/LICENSE",
                }
            ):
                pass
            else:
                raise PrivacyError("archive-entry-not-allowlisted", entry)
            check_text(data, entry, terms)
    if required - seen:
        raise PrivacyError("archive-source-missing", sorted(required - seen)[0])
    if kind == "wheel":
        check_wheel_metadata(root, entries, version)
    return {"ok": True, "archive_entries": len(seen)}


def public_demo(root, language):
    """Deterministic demo, regenerated from pinned synthetic inputs, never from out/."""
    from .indexer import build_index
    from .languages import adapter_for
    from .business import extract_business
    from .render import render

    root = Path(root)
    check_source(root)
    policy = read_policy(root)
    spec = policy["public_demo"]
    manifest_path = root / spec["manifest"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    repo = (manifest_path.parent / manifest.get("repository", ".")).resolve()
    notes = json.loads((root / spec["explanations"][language]).read_text(encoding="utf-8"))
    if repo != manifest_path.parent.resolve():
        raise PrivacyError("demo-outside-fixture", spec["manifest"])
    with tempfile.TemporaryDirectory() as temp:
        index = build_index(repo, adapter_for("rust"), Path(temp) / "cache")
        facts = extract_business(index, manifest, 0, 64)
        facts["title"] = manifest["title"]
        facts["output_language"] = language
        facts["generated_utc"] = "2000-01-01T00:00:00Z"
        facts["index_stats"] = {"fixture": "synthetic public example; fixed demo timestamp"}
        output = Path(temp) / "demo.html"
        stats = render(facts, notes, output, manifest["title"], output_language=language)
        if (
            stats["stale_cards"]
            or stats["needs_translation"]
            or stats["explained"] != len(manifest["nodes"])
        ):
            raise PrivacyError("demo-evidence-not-current", "public-demo")
        return output.read_bytes()


def check_asset(root, asset, require_terms=False):
    root = Path(root)
    asset = Path(asset)
    if asset.is_symlink():
        raise PrivacyError("asset-symlink", asset.name)
    terms = terms_for(root, require_terms)
    check_source(root, require_terms)
    if asset.suffix in {".zip", ".whl"}:
        return check_archive(root, asset, terms)
    demos = {"code-review-kit-demo.html": "zh", "code-review-kit-demo-en.html": "en"}
    if asset.name in demos:
        data = asset.read_bytes()
        check_text(data, asset.name, terms, allow_report=True)
        if data.replace(b"\r\n", b"\n") != public_demo(root, demos[asset.name]).replace(
            b"\r\n", b"\n"
        ):
            raise PrivacyError("html-not-approved-synthetic-demo", asset.name)
        return {"ok": True, "synthetic_demo": demos[asset.name]}
    raise PrivacyError("asset-not-allowlisted", asset.name)


def check_sdist(root, asset):
    root = Path(root)
    policy = read_policy(root)
    terms = terms_for(root)
    seen = set()
    total = 0
    version = version_for(root)
    prefixes = {f"code_review_kit-{version}", f"code-review-kit-{version}"}
    with tarfile.open(asset, "r:gz") as archive:
        for member in archive.getmembers():
            if member.isdir():
                continue
            if not member.isfile():
                raise PrivacyError("sdist-link", member.name)
            parts = PurePosixPath(member.name).parts
            if not parts or parts[0] not in prefixes:
                raise PrivacyError("sdist-prefix", member.name)
            name = safe_name("/".join(parts[1:]))
            if name in seen:
                raise PrivacyError("sdist-duplicate", name)
            seen.add(name)
            total += member.size
            if total > MAX_BYTES:
                raise PrivacyError("sdist-too-large", "sdist")
            data = archive.extractfile(member).read()
            if name == POLICY or name in policy["source_hashes"]:
                check_source_entry(name, data, policy, terms)
            elif name in {"PKG-INFO", "setup.cfg"} or re.fullmatch(
                r"code_review_kit\.egg-info/(PKG-INFO|SOURCES\.txt|dependency_links\.txt|entry_points\.txt|requires\.txt|top_level\.txt)",
                name,
            ):
                check_text(data, name, terms)
            else:
                raise PrivacyError("sdist-entry-not-allowlisted", name)
    if not (set(policy["source_hashes"]) | {POLICY}) <= seen:
        raise PrivacyError("sdist-source-missing", "sdist")
    return {"ok": True, "source_archive_entries": len(seen)}


def check_push(root, lines):
    """Inspect pushed commit snapshots, not merely the current working tree."""
    root = Path(root)
    terms = terms_for(root, True)
    commits = set()
    for line in lines:
        local_ref, new, remote_ref, old = line.split()
        check_text((local_ref + " " + remote_ref).encode(), "push-ref", terms)
        if new == "0" * 40:
            continue
        if not re.fullmatch("[a-f0-9]{40}", new + "") or not re.fullmatch("[a-f0-9]{40}", old):
            raise PrivacyError("invalid-push-ref", "push-ref")
        commits.add(new)
        args = ["git", "rev-list", new]
        args += ["^" + old] if old != "0" * 40 else ["--not", "--remotes"]
        commits.update(subprocess.check_output(args, cwd=root).decode().splitlines())
    for commit in commits:
        message = subprocess.check_output(["git", "show", "-s", "--format=%B", commit], cwd=root)
        check_text(message, "commit-message", terms)
        raw = subprocess.check_output(["git", "archive", commit], cwd=root)
        if len(raw) > MAX_BYTES:
            raise PrivacyError("snapshot-too-large", "push-snapshot")
        with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
            entries = {}
            for member in archive.getmembers():
                if member.isdir():
                    continue
                if not member.isfile():
                    raise PrivacyError("snapshot-symlink", member.name)
                name = safe_name(member.name)
                entries[name] = archive.extractfile(member).read()
            if POLICY not in entries:
                raise PrivacyError("snapshot-policy-missing", "push-snapshot")
            policy = json.loads(entries[POLICY])
            if set(entries) != set(policy["source_hashes"]) | {POLICY}:
                raise PrivacyError("snapshot-source-set-mismatch", "push-snapshot")
            for name, data in entries.items():
                check_source_entry(name, data, policy, terms)
    return {"ok": True, "pushed_snapshots": len(commits)}
