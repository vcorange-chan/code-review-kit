"""Execute the exact release ZIP in an isolated folder; no agent/model calls."""

from pathlib import Path
import tempfile
import subprocess
import sys
import zipfile
import json
import os
import shutil

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
    # Research commands run from the packaged tool, not a developer checkout.
    found = json.loads(
        run(
            skill / "scripts/review.py",
            "locate",
            "--repo",
            ROOT / "examples/document-pipeline",
            "--query",
            "reduce_event",
            "--out",
            folder / "research",
            "--cache",
            folder / "cache",
        )
    )
    assert found["candidates"] == 1 and Path(found["html"]).exists()
    facet = json.loads(
        run(
            skill / "scripts/review.py",
            "dossier",
            "--facts",
            folder / "research/facts.json",
            "--symbol",
            "reduce_event",
            "--facet",
            "branches",
            "--out",
            folder / "dossier",
            "--bytes",
            "3000",
        )
    )
    assert facet["operation"] == "function.branches" and facet["rows"]
    session = folder / "investigation"
    run(
        skill / "scripts/review.py",
        "investigate",
        "import",
        "--session",
        session,
        "--input",
        folder / "research/evidence.json",
    )
    record = folder / "finding.json"
    record.write_text(
        json.dumps(
            {
                "kind": "finding",
                "text": "An event reducer has explicit guards.",
                "support": [facet["id"]],
            }
        ),
        encoding="utf-8",
    )
    saved = json.loads(
        run(
            skill / "scripts/review.py",
            "investigate",
            "record",
            "--session",
            session,
            "--input",
            record,
            "--expected-revision",
            "0",
        )
    )
    assert saved["revision"] == 1
    run(
        skill / "scripts/review.py",
        "investigate",
        "render",
        "--session",
        session,
        "--out",
        folder / "investigation.html",
    )
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
    tutor_facet = json.loads(run(skill / "scripts/review.py", "dossier", "--facts", folder / "tutor-facts/facts.json",
                                 "--symbol", "run", "--facet", "signature", "--out", folder / "tutor-dossier", "--bytes", "3000"))
    assert tutor_facet["operation"] == "function.signature"
    # Exercise the packaged mechanical operations, including a complete old revision.
    lesson = folder / "lesson.json"
    shutil.copyfile(ROOT / "examples/document-pipeline/lecture.zh.json", lesson)
    facts = folder / "tutor-facts/facts.json"
    run(skill / "scripts/review.py", "lecture", "--lecture", lesson, "--facts", facts, "--accept-new")
    replacement = folder / "replacement.json"
    replacement.write_text(json.dumps({"goal": "Explain the same fixed source another way"}), encoding="utf-8")
    revised = json.loads(run(skill / "scripts/review.py", "tutor", "retell", "--lecture", lesson,
                             "--facts", facts, "--step", "s1", "--expected-revision", "1", "--replacement", replacement))
    assert revised["r"] == 2
    packet = json.loads(run(skill / "scripts/review.py", "tutor", "packet", "--lecture", lesson,
                            "--facts", facts, "--step", "s1", "--revision", "1", "--bytes", "3000", "--out", folder / "step.json"))
    assert packet["bytes"] <= 3000
    next_step = json.loads(run(skill / "scripts/review.py", "tutor", "next", "--lecture", lesson,
                               "--step", "s1", "--expected-revision", "2"))
    assert next_step["current"] == "s2" and next_step["position_only"]
    discussion = folder / "discussion.jsonl"
    record = folder / "record.json"
    record.write_text(json.dumps({"step": "s1", "revision": 1, "kind": "ask", "quote": "original",
                                  "question": "why", "answer": "full answer"}), encoding="utf-8")
    run(skill / "scripts/review.py", "discuss", "--lecture", lesson, "--discussion", discussion, "--record-file", record)
    personal = json.loads(run(skill / "scripts/review.py", "lecture", "--lecture", lesson,
                              "--facts", facts, "--discussion", discussion))
    assert personal["discussion_records"] == 1 and personal["source_locked"]
    run(skill / "scripts/review.py", "business", "--manifest", ROOT / "examples/document-pipeline/events-business.json",
        "--language", "python", "--depth", "0", "--out", folder / "event-facts")
    events = json.loads(run(skill / "scripts/review.py", "lecture", "--lecture", ROOT / "examples/document-pipeline/events-lecture.zh.json",
                            "--facts", folder / "event-facts/facts.json", "--html", folder / "events.html"))
    assert events["steps"] == 4 and not events["stale_steps"]
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
                "event_steps": events["steps"],
                "tutor_operations_executed": True,
                "research_operations_executed": True,
            }
        )
    )
