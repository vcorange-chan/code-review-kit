"""Build a self-contained skill ZIP from a source allowlist; never bundle user data."""

from pathlib import Path
import zipfile
import hashlib
import json
import sys
import tempfile
import os

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reviewkit.release_privacy import check_source, read_policy, skill_mapping, check_asset


def build(out=None):
    check_source(ROOT)
    out = Path(out or ROOT / "dist")
    out.mkdir(parents=True, exist_ok=True)
    target = out / "code-review-kit-skill.zip"
    with tempfile.TemporaryDirectory(dir=out) as temp:
        candidate = Path(temp) / target.name
        with zipfile.ZipFile(candidate, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, source in sorted(skill_mapping(read_policy(ROOT)).items()):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.external_attr = 0o644 << 16
                archive.writestr(
                    info, (ROOT / source).read_bytes(), compress_type=zipfile.ZIP_DEFLATED
                )
        check_asset(ROOT, candidate)
        os.replace(candidate, target)
    metadata = {
        "file": target.name,
        "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "bytes": target.stat().st_size,
        "native_dependencies_bundled": False,
    }
    (out / "skill-build.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(metadata))
    return target


if __name__ == "__main__":
    build()
