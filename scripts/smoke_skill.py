"""Execute the exact release ZIP in an isolated folder; no agent/model calls."""

from pathlib import Path
import tempfile
import subprocess
import sys
import zipfile
import json
import os

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as temp:
    folder = Path(temp)
    with zipfile.ZipFile(ROOT / "dist/code-review-kit-skill.zip") as archive:
        archive.extractall(folder)
    skill = folder / "code-review-kit"
    state = folder / "writable-state"

    def run(*args):
        result = subprocess.run(
            [sys.executable, *map(str, args)],
            cwd=skill,
            text=True,
            capture_output=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONUTF8": "1", "CODE_REVIEW_KIT_STATE": str(state)},
        )
        if result.returncode:
            raise RuntimeError(result.stderr + "\n" + result.stdout)
        return result.stdout

    # Unix runners exercise the same immutable-package shape used by mounted skills.
    if os.name != "nt":
        for path in sorted(skill.rglob("*"), reverse=True):
            path.chmod(0o555 if path.is_dir() else 0o444)
        skill.chmod(0o555)
    run(skill / "scripts/setup.py")
    doctor = json.loads(run(skill / "scripts/review.py", "doctor"))
    output = folder / "report"
    report = json.loads(
        run(
            skill / "scripts/review.py",
            "business",
            "--manifest",
            ROOT / "examples/document-pipeline/business.json",
            "--repo",
            ROOT / "examples/document-pipeline",
            "--explanations",
            ROOT / "examples/document-pipeline/explanations.json",
            "--depth",
            "0",
            "--max-nodes",
            "64",
            "--out",
            output,
            "--cache",
            folder / "cache",
        )
    )
    assert (
        doctor["ok"]
        and report["cards"] == 14
        and report["explained"] == 14
        and not report["stale_cards"]
    )
    assert state.is_dir() and not (skill / "scripts/tool/.deps").exists()
    english = json.loads(
        run(
            skill / "scripts/review.py",
            "business",
            "--manifest",
            ROOT / "examples/document-pipeline/business.json",
            "--repo",
            ROOT / "examples/document-pipeline",
            "--explanations",
            ROOT / "examples/document-pipeline/explanations.en.json",
            "--output-language",
            "en",
            "--depth",
            "0",
            "--max-nodes",
            "64",
            "--out",
            folder / "report-en",
            "--cache",
            folder / "cache",
        )
    )
    assert (
        english["output_language"] == "en"
        and english["explained"] == 14
        and not english["needs_translation"]
    )
    assert '<html lang="en">' in (folder / "report-en/index.html").read_text(encoding="utf-8")
    if os.name != "nt":
        skill.chmod(0o755)
        for path in skill.rglob("*"):
            path.chmod(0o755 if path.is_dir() else 0o644)
    print(
        json.dumps(
            {
                "zip_executed": True,
                "cards": 14,
                "stale_cards": report["stale_cards"],
                "native_platform_install": True,
                "dependency_state_outside_skill": True,
            }
        )
    )
