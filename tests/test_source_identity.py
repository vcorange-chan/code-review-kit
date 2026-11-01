from pathlib import Path
import copy
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / ".deps")]
from reviewkit.source_identity import capture_source, commit_checkout, verify_source
from reviewkit.storage import digest


class SourceIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.run_git("init")
        self.run_git("config", "user.email", "demo@example.invalid")
        self.run_git("config", "user.name", "Demo")
        self.run_git("config", "core.autocrlf", "false")
        self.raw = b'\xef\xbb\xbfdef accept(value):\r\n    return value\r\n'
        (self.repo / "demo.py").write_bytes(self.raw)
        self.run_git("add", ".")
        self.run_git("-c", "core.autocrlf=false", "commit", "-m", "demo")
        self.commit = self.run_git("rev-parse", "HEAD").strip()
        self.facts = {
            "functions": [{"id": "demo.py::accept", "file": "demo.py", "line": 1, "end_line": 2,
                           "source": "def accept(value):\n    return value"}],
            "source_files": {"demo.py": digest(self.raw)}, "limits": {"depth": 0},
        }

    def run_git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args], stderr=subprocess.DEVNULL).decode()

    def test_portable_snapshot_preserves_bom_crlf_and_rejects_tamper(self):
        capture_source(self.facts, self.repo)
        self.assertEqual(self.facts["source_snapshot"]["mode"], "git_commit")
        verify_source(self.facts)
        changed = copy.deepcopy(self.facts)
        changed["functions"][0]["source"] = "invented source"
        with self.assertRaisesRegex(ValueError, "Node does not match"):
            verify_source(changed)
        changed = copy.deepcopy(self.facts)
        changed["source_snapshot"]["commit"] = "wrong"
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            verify_source(changed)

    def test_dirty_workspace_is_not_mislabeled_as_commit(self):
        (self.repo / "notes.txt").write_text("untracked", encoding="utf-8")
        capture_source(self.facts, self.repo)
        self.assertEqual(self.facts["source_snapshot"]["mode"], "workspace")
        self.assertTrue(self.facts["source_snapshot"]["worktree_dirty"])

    def test_fixed_commit_ignores_dirty_workspace_and_cleans_temp(self):
        (self.repo / "demo.py").write_text("raise RuntimeError('do not run')", encoding="utf-8")
        with commit_checkout(self.repo, self.commit) as (tree, origin):
            self.assertEqual((tree / "demo.py").read_bytes(), self.raw)
            capture_source(self.facts, tree, origin)
            self.assertEqual(self.facts["source_snapshot"]["mode"], "git_commit")
        self.assertFalse(tree.exists())
        self.assertIn("do not run", (self.repo / "demo.py").read_text())

    def test_changed_between_index_and_capture_refuses(self):
        (self.repo / "demo.py").write_text("different", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed during extraction"):
            capture_source(self.facts, self.repo)


if __name__ == "__main__":
    unittest.main()
