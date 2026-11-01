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
    assert '<html lang="en">' in (folder / "report-en/index.html").read_text(
        encoding="utf-8"
    )
    for language, relative, symbol in [
        ("python", "polyglot/service.py", "normalize_document"),
        ("dart", "polyglot/client.dart", "prepareRequest"),
    ]:
        summary = json.loads(
            run(
                skill / "scripts/review.py",
                "function",
                "--repo",
                ROOT / "examples/document-pipeline",
                "--language",
                language,
                "--file",
                relative,
                "--symbol",
                symbol,
                "--out",
                folder / ("single-" + language),
                "--cache",
                folder / "cache",
            )
        )
        assert summary["cards"] == 1
    for language in ["zh", "en"]:
        mixed = json.loads(
            run(
                skill / "scripts/review.py",
                "business",
                "--manifest",
                ROOT / "examples/document-pipeline/mixed-business.json",
                "--explanations",
                ROOT / f"examples/document-pipeline/mixed-explanations.{language}.json",
                "--output-language",
                language,
                "--depth",
                "0",
                "--out",
                folder / ("mixed-" + language),
                "--cache",
                folder / "cache",
            )
        )
        assert (
            mixed["cards"] == 3 and mixed["explained"] == 3 and not mixed["stale_cards"]
        )
    if os.name != "nt":
        skill.chmod(0o755)
        for path in skill.rglob("*"):
            path.chmod(0o755 if path.is_dir() else 0o644)
    # The tutor ZIP installs alone: its own copy of the tool extracts facts and renders a lecture.
    with zipfile.ZipFile(ROOT / "dist/copy-tutor-skill.zip") as archive:
        archive.extractall(folder)
    skill = folder / "copy-tutor"
    run(skill / "scripts/review.py", "doctor")
    run(
        skill / "scripts/review.py",
        "function",
        "--repo",
        ROOT / "examples/document-pipeline",
        "--language",
        "rust",
        "--file",
        "src/lib.rs",
        "--symbol",
        "run",
        "--depth",
        "1",
        "--max-nodes",
        "32",
        "--out",
        folder / "tutor-facts",
        "--cache",
        folder / "cache",
    )
    lecture = json.loads(
        run(
            skill / "scripts/review.py",
            "lecture",
            "--lecture",
            ROOT / "examples/document-pipeline/lecture.zh.json",
            "--facts",
            folder / "tutor-facts/facts.json",
            "--html",
            folder / "lecture/index.html",
        )
    )
    assert lecture["steps"] == 3 and not lecture["stale_steps"] and not lecture["unbound_steps"]
    print(
        json.dumps(
            {
                "zip_executed": True,
                "cards": 14,
                "stale_cards": report["stale_cards"],
                "native_platform_install": True,
                "dependency_state_outside_skill": True,
                "languages": doctor["languages"],
                "mixed_cards": 3,
                "lecture_steps": lecture["steps"],
            }
        )
    )
