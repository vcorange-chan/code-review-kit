"""All names and paths constructed here are fictional, never real project data."""

from pathlib import Path
from test_reviewkit import HOME  # Reuse the test suite's trusted parser dependency setup.
import json, subprocess, tempfile, unittest, zipfile, os
from unittest.mock import patch
from reviewkit.release_privacy import (
    PrivacyError,
    check_source,
    check_asset,
    check_text,
    check_push,
    digest,
    public_demo,
    terms_for,
)


class ReleasePrivacyTests(unittest.TestCase):
    def test_investigation_outputs_are_private_even_if_renamed(self):
        for value in [
            {"queries": [], "scope_id": "fictional", "candidates": []},
            {"dossiers": []},
            {"source_identities": [], "history": [], "records": []},
            {"evidence": [{"id": "ev_" + "a" * 64}]},
        ]:
            with self.subTest(value=value), self.assertRaises(PrivacyError):
                check_text(json.dumps(value).encode(), "renamed.json")
        with self.assertRaises(PrivacyError):
            check_text(
                b'<main><section id="investigation"></section></main>', "renamed.html"
            )


    def test_generated_report_cannot_hide_as_wheel_metadata(self):
        self.files["README.md"] = b"# Fictional fixture\n"
        (self.root / "README.md").write_bytes(self.files["README.md"])
        self.approve()
        target = self.root / "code_review_kit-0.0.1-py3-none-any.whl"
        with zipfile.ZipFile(target, "w") as z:
            z.writestr("reviewkit/app.py", self.files["reviewkit/app.py"])
            z.writestr(
                "code_review_kit-0.0.1.dist-info/METADATA", b"<html>fictional private report</html>"
            )
        with self.assertRaises(PrivacyError):
            check_asset(self.root, target)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.files = {
            "reviewkit/app.py": b"value = 1\n",
            "pyproject.toml": b'[project]\nversion = "0.0.1"\n',
            ".gitignore": b".local/\n",
        }
        for name, data in self.files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.approve()

    def tearDown(self):
        self.temp.cleanup()

    def approve(self):
        policy = {
            "schema_version": 1,
            "source_hashes": {name: digest((self.root / name).read_bytes()) for name in self.files},
        }
        (self.root / ".release-policy.json").write_text(json.dumps(policy), encoding="utf-8")

    def path_example(self):
        return chr(67) + ":/" + "Users/" + "FictionalPerson" + "/project.rs"

    def test_clean_source_and_changed_hash(self):
        self.assertTrue(check_source(self.root)["ok"])
        (self.root / "reviewkit/app.py").write_text("value = 2")
        with self.assertRaisesRegex(PrivacyError, "source-not-reviewed"):
            check_source(self.root)

    def test_ignored_stray_package_source_is_rejected(self):
        (self.root / "reviewkit/extra_private.rs").write_text("fictional source")
        with self.assertRaises(PrivacyError):
            check_source(self.root)

    def test_host_paths_are_blocked_even_with_an_approved_hash(self):
        (self.root / "reviewkit/app.py").write_text(self.path_example())
        self.approve()
        with self.assertRaisesRegex(PrivacyError, "host-absolute-path") as raised:
            check_source(self.root)
        self.assertNotIn("FictionalPerson", str(raised.exception))

    def test_private_terms_do_not_appear_in_diagnostics(self):
        with self.assertRaises(PrivacyError) as raised:
            check_text(b"A VelvetToy label", "note", ["velvettoy"])
        self.assertNotIn("VelvetToy", str(raised.exception))

    def test_review_data_and_generated_html_are_rejected(self):
        for data in [
            b'{"root_ids":[],"card_evidence":{}}',
            b'<section class="stage" data-status="current"></section>',
        ]:
            with self.assertRaises(PrivacyError):
                check_text(data, "review.html")

    def test_archive_unknown_review_and_traversal_entries_are_rejected(self):
        target = self.root / "code-review-kit-skill.zip"
        for name in [
            "code-review-kit/out/facts.json",
            "../escape.py",
            "code-review-kit/scripts/tool/reviewkit/extra.rs",
        ]:
            with zipfile.ZipFile(target, "w") as z:
                z.writestr(name, b"fictional")
            with self.assertRaises(PrivacyError):
                check_asset(self.root, target)

    def test_archive_approved_file_cannot_be_replaced(self):
        target = self.root / "code-review-kit-skill.zip"
        with zipfile.ZipFile(target, "w") as z:
            z.writestr("code-review-kit/scripts/tool/reviewkit/app.py", b"changed = 3")
        with self.assertRaisesRegex(PrivacyError, "archive-source-mismatch"):
            check_asset(self.root, target)

    def test_archive_requires_all_expected_sources(self):
        target = self.root / "code-review-kit-skill.zip"
        with zipfile.ZipFile(target, "w"):
            pass
        with self.assertRaisesRegex(PrivacyError, "archive-source-missing"):
            check_asset(self.root, target)

    def test_private_policy_missing_or_invalid_fails_closed(self):
        with patch.dict(os.environ, {"REVIEW_KIT_PRIVATE_TERMS": ""}):
            with self.assertRaisesRegex(PrivacyError, "private-policy-required"):
                terms_for(self.root, True)
        with patch.dict(os.environ, {"REVIEW_KIT_PRIVATE_TERMS": "{}"}):
            with self.assertRaisesRegex(PrivacyError, "invalid-private-policy"):
                terms_for(self.root)

    def test_renaming_a_private_html_does_not_make_it_a_demo(self):
        actual = Path(__file__).resolve().parents[1]
        path = self.root / "code-review-kit-demo.html"
        path.write_text("<html>fictional private review</html>")
        with self.assertRaisesRegex(PrivacyError, "html-not-approved-synthetic-demo"):
            check_asset(actual, path)

    def test_public_demo_is_reproducible(self):
        actual = Path(__file__).resolve().parents[1]
        self.assertEqual(public_demo(actual, "en"), public_demo(actual, "en"))

    def test_push_inspects_intermediate_commits(self):
        def git(*args):
            return (
                subprocess.check_output(["git", *args], cwd=self.root, stderr=subprocess.DEVNULL)
                .decode()
                .strip()
            )

        git("init", "--quiet")

        def commit():
            git("add", *self.files, ".release-policy.json")
            git(
                "-c",
                "user.name=Demo",
                "-c",
                "user.email=demo@example.invalid",
                "commit",
                "--quiet",
                "-m",
                "Synthetic test snapshot",
            )
            return git("rev-parse", "HEAD")

        old = commit()
        (self.root / "reviewkit/app.py").write_text(self.path_example())
        self.approve()
        commit()
        (self.root / "reviewkit/app.py").write_bytes(self.files["reviewkit/app.py"])
        self.approve()
        tip = commit()
        config = self.root / ".local/privacy-denylist.json"
        config.parent.mkdir()
        config.write_text('["VelvetToy"]')
        with self.assertRaisesRegex(PrivacyError, "host-absolute-path"):
            check_push(self.root, [f"refs/heads/main {tip} refs/heads/main {old}"])
