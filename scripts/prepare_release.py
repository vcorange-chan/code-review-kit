"""Prepare approved public assets; publish only after rechecking the actual files."""

from pathlib import Path
import argparse, hashlib, json, shutil, subprocess, sys, tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reviewkit.runtime import dependency_paths

sys.path[:0] = [str(p) for p in dependency_paths(ROOT)]
from reviewkit.release_privacy import (
    check_source,
    check_asset,
    check_text,
    terms_for,
    public_demo,
    version_for,
    read_policy,
    PrivacyError,
)
from scripts.build_dist import build


def names():
    return [
        "code-review-kit-skill.zip",
        f"code_review_kit-{version_for(ROOT)}-py3-none-any.whl",
        "code-review-kit-demo.html",
        "code-review-kit-demo-en.html",
    ]


def checksums(folder):
    return "".join(
        hashlib.sha256((folder / name).read_bytes()).hexdigest() + "  " + name + "\n"
        for name in names()
    )


def verify(folder):
    check_source(ROOT, True)
    allowed = set(names()) | {"SHA256SUMS.txt"}
    if {p.name for p in folder.iterdir()} != allowed:
        raise PrivacyError("unapproved-release-directory-entry", "release-directory")
    if any(p.is_symlink() or not p.is_file() for p in folder.iterdir()):
        raise PrivacyError("release-symlink-or-directory", "release-directory")
    for name in names():
        path = folder / name
        if path.is_symlink():
            raise PrivacyError("release-symlink", name)
        check_asset(ROOT, path, True)
    if (folder / "SHA256SUMS.txt").read_text(encoding="utf-8") != checksums(folder):
        raise PrivacyError("release-checksum-mismatch", "checksums")
    return {"ok": True, "checked_assets": len(names()), "synthetic_demos_only": True}


def prepare(folder):
    check_source(ROOT, True)
    if folder.exists() and any(folder.iterdir()):
        raise PrivacyError("release-output-must-be-empty", "release-directory")
    folder.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        staging = Path(temp)
        build(staging)
        shutil.copyfile(staging / names()[0], folder / names()[0])
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                str(ROOT),
                "--no-deps",
                "--wheel-dir",
                str(staging),
            ],
            capture_output=True,
        )
        if result.returncode:
            raise PrivacyError("wheel-build-failed", "wheel")
        shutil.copyfile(staging / names()[1], folder / names()[1])
    (folder / names()[2]).write_bytes(public_demo(ROOT, "zh"))
    (folder / names()[3]).write_bytes(public_demo(ROOT, "en"))
    (folder / "SHA256SUMS.txt").write_text(checksums(folder), encoding="utf-8")
    return verify(folder)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(ROOT / "dist/release"))
    parser.add_argument("--verify", action="store_true")
    parser.add_argument(
        "--publish", help="Explicit release tag; always rechecks assets before upload"
    )
    parser.add_argument("--target")
    parser.add_argument("--notes")
    args = parser.parse_args()
    folder = Path(args.out).resolve()
    try:
        result = verify(folder) if args.verify or args.publish else prepare(folder)
        if args.publish:
            if args.publish != "v" + version_for(ROOT) or not args.target or not args.notes:
                raise PrivacyError("release-version-target-notes-required", "publish")
            head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
            if (
                args.target != head
                or subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT).strip()
            ):
                raise PrivacyError("release-needs-clean-matching-commit", "publish")
            note_path = Path(args.notes)
            check_text(note_path.read_bytes(), "release-notes", terms_for(ROOT, True))
            repo = read_policy(ROOT)["github_repository"]
            command = [
                "gh",
                "release",
                "create",
                args.publish,
                "--repo",
                repo,
                "--target",
                head,
                "--title",
                args.publish,
                "--notes-file",
                str(note_path),
            ]
            command += [str(folder / name) for name in [*names(), "SHA256SUMS.txt"]]
            subprocess.run(command, cwd=ROOT, check=True)
            result["published"] = args.publish
        print(json.dumps(result))
        return 0
    except Exception as error:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": (
                        str(error)
                        if isinstance(error, PrivacyError)
                        else "Release preparation failed: " + type(error).__name__
                    ),
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
