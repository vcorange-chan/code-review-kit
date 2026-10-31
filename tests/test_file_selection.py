"""Both candidate providers must obey the same repository-local ignore policy."""

import os
import shutil
import subprocess
from unittest.mock import patch
from test_reviewkit import RepositoryTestCase
from reviewkit.indexer import source_files, build_index
from reviewkit.languages import adapter_for

RG = shutil.which("rg")


class FileSelectionTests(RepositoryTestCase):
    def both(self, suffixes=(".py",)):
        candidates = [
            p.relative_to(self.repo).as_posix()
            for p in self.repo.rglob("*")
            if p.is_file()
        ]
        result = subprocess.CompletedProcess(
            ["rg"], 0, "\0".join(candidates) + "\0", ""
        )
        with patch("reviewkit.indexer.shutil.which", return_value="rg"), patch(
            "reviewkit.indexer.subprocess.run", return_value=result
        ):
            fast, finder = source_files(self.repo, suffixes)
            self.assertEqual(finder, "rg")
        with patch("reviewkit.indexer.shutil.which", return_value=None):
            slow, finder = source_files(self.repo, suffixes)
            self.assertEqual(finder, "python-walk")
        self.assertEqual(fast, slow)
        return slow

    def test_gitignore_applies_even_without_a_git_checkout(self):
        self.put(".gitignore", "ignored.py\n")
        self.put("visible.py", "pass")
        self.put("ignored.py", "pass")
        self.assertEqual(self.both(), ["visible.py"])

    def test_nested_rules_negation_and_directory_pruning(self):
        self.put(".gitignore", "*.py\n!src/keep.py\nclosed/\n!closed/keep.py\n")
        self.put("src/.gitignore", "!other.py\nprivate.py\n")
        for name in [
            "root.py",
            "src/keep.py",
            "src/other.py",
            "src/private.py",
            "closed/keep.py",
        ]:
            self.put(name, "pass")
        self.assertEqual(self.both(), ["src/keep.py", "src/other.py"])

    def test_root_anchored_patterns_and_nested_rule_roots(self):
        self.put(".gitignore", "/root_only.py\n")
        self.put("pkg/.gitignore", "/private.py\n")
        names = [
            "root_only.py",
            "pkg/root_only.py",
            "private.py",
            "pkg/private.py",
            "pkg/sub/private.py",
        ]
        for name in names:
            self.put(name, "pass")
        self.assertEqual(
            self.both(), ["pkg/root_only.py", "pkg/sub/private.py", "private.py"]
        )

    def test_ignore_and_rgignore_have_shared_precedence(self):
        self.put(".gitignore", "*.py\n")
        self.put(".ignore", "!keep.py\n")
        self.put(".rgignore", "!override.py\n")
        self.put("pkg/.gitignore", "override.py\n")
        for name in ["keep.py", "other.py", "pkg/override.py"]:
            self.put(name, "pass")
        self.assertEqual(self.both(), ["keep.py", "pkg/override.py"])

    def test_generated_private_directories_cannot_be_reincluded(self):
        self.put(".gitignore", "!out/\n!.local/\n")
        for folder in [
            "out",
            ".local",
            ".cache",
            "node_modules",
            ".venv",
            ".git",
            "nested/out",
            "nested/.local",
        ]:
            self.put(folder + "/hidden.py", "pass")
        self.put("src/out.py", "pass")
        self.assertEqual(self.both(), ["src/out.py"])

    def test_language_suffixes_unicode_spaces_and_escaped_patterns(self):
        self.put(".gitignore", "\\#ignored.py\n\\!ignored.py\n# a comment\n")
        for name in [
            "#ignored.py",
            "!ignored.py",
            "folder with space/示例.py",
            ".hidden/ok.py",
            "main.dart",
            "lib.rs",
            "note.txt",
        ]:
            self.put(name, "pass")
        self.assertEqual(
            self.both((".py", ".dart", ".rs")),
            [".hidden/ok.py", "folder with space/示例.py", "lib.rs", "main.dart"],
        )

    def test_explicit_repository_does_not_inherit_parent_ignore_files(self):
        (self.root / ".gitignore").write_text("*.py\n")
        self.put("visible.py", "pass")
        self.assertEqual(self.both(), ["visible.py"])

    def test_ignore_edits_update_the_index_and_remove_old_entries(self):
        for name in ["keep.py", "drop.py"]:
            self.put(name, "def run():\n    pass\n")
        with patch("reviewkit.indexer.shutil.which", return_value=None):
            build_index(self.repo, adapter_for("python"), self.cache)
            self.put(".gitignore", "drop.py\n")
            updated = build_index(self.repo, adapter_for("python"), self.cache)
        self.assertEqual(set(updated["files"]), {"keep.py"})
        self.assertEqual(updated["stats"]["removed_files"], 1)

    def test_source_symlinks_are_excluded_by_both_providers(self):
        self.put("visible.py", "pass")
        try:
            (self.repo / "link.py").symlink_to(self.repo / "visible.py")
        except OSError:
            self.skipTest("This platform does not permit unprivileged symlinks")
        self.assertEqual(self.both(), ["visible.py"])

    def test_unreadable_walk_is_an_error_instead_of_a_partial_success(self):
        def denied(root, *, onerror, followlinks):
            onerror(PermissionError("fictional inaccessible directory"))
            yield

        with patch("reviewkit.indexer.shutil.which", return_value=None), patch(
            "reviewkit.indexer.os.walk", denied
        ):
            with self.assertRaises(PermissionError):
                source_files(self.repo, (".py",))

    def test_real_rg_and_walk_agree_with_native_rg_config_disabled(self):
        if not RG:
            self.skipTest(
                "rg is not installed; both provider policies are covered above"
            )
        self.put(".gitignore", "secret.py\n")
        for name in [
            "secret.py",
            "visible.py",
            "nested/.local/helper.py",
            "out/report.py",
        ]:
            self.put(name, "pass")
        config = self.root / "rg-config"
        config.write_text("--glob\n!*.py\n")
        with patch.dict(os.environ, {"RIPGREP_CONFIG_PATH": str(config)}):
            with patch("reviewkit.indexer.shutil.which", return_value=RG):
                fast, _ = source_files(self.repo, (".py",))
            with patch("reviewkit.indexer.shutil.which", return_value=None):
                slow, _ = source_files(self.repo, (".py",))
        self.assertEqual(fast, ["visible.py"])
        self.assertEqual(fast, slow)
