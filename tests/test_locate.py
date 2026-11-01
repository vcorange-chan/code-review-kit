from pathlib import Path
import tempfile
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / ".deps")]
from reviewkit.indexer import build_index
from reviewkit.languages import adapter_for
from reviewkit.locate import locate


class LocateTests(unittest.TestCase):
    def test_path_hit_does_not_invent_a_function_owner(self):
        result = locate(
            self.index({"billing.py": "def unrelated():\n    return 1\n"}), ["billing"]
        )
        self.assertIsNone(result["candidates"][0]["node_id"])
        self.assertEqual(result["candidates"][0]["status"], "source_context_only")

    def test_parse_failures_are_reported_and_missing_search_is_not_absence_proof(self):
        index = self.index(
            {"broken.py": "def bad(:\n", "good.py": "def ok():\n    return 1\n"}
        )
        result = locate(index, ["missing"])
        self.assertEqual(result["candidates"], [])
        self.assertEqual(result["coverage"]["parse_error_files"], ["broken.py"])
        self.assertIn(
            "dynamic_strings_generated_code_unindexed_files_not_proven_absent",
            result["limits"],
        )

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def index(self, files):
        for name, source in files.items():
            (self.root / name).write_text(source, encoding="utf-8")
        return build_index(self.root, adapter_for("auto"), self.root / "cache")

    def test_all_languages_string_comment_and_function_hits(self):
        index = self.index(
            {
                "demo.rs": 'pub fn rust_import() { let msg = "导入失败"; }\n',
                "demo.py": 'def python_import():\n    # retry_hint\n    raise ValueError("导入失败")\n',
                "demo.dart": 'String dartImport() { return "导入失败"; }\n',
            }
        )
        result = locate(index, ["导入失败"])
        self.assertEqual(
            {r["language"] for r in result["candidates"]}, {"rust", "python", "dart"}
        )
        self.assertTrue(
            all(
                r["node_id"] and r["status"] == "syntax_candidate"
                for r in result["candidates"]
            )
        )
        comment = locate(index, ["retry_hint"])["candidates"][0]
        self.assertEqual(comment["name"], "python_import")
        self.assertEqual(comment["signals"][0]["kind"], "comment")

    def test_symbol_rank_context_and_limits_are_honest(self):
        index = self.index(
            {
                "demo.py": 'TITLE = "import_failed"\ndef import_failed():\n    return TITLE\ndef other():\n    return "import_failed"\n'
            }
        )
        result = locate(index, ["import_failed"], limit=1)
        self.assertEqual(result["candidates"][0]["name"], "import_failed")
        self.assertTrue(result["coverage"]["truncated"])
        self.assertEqual(result["coverage"]["total_candidates"], 3)
        self.assertFalse(locate(index, ["not_present"])["candidates"])

    def test_match_all_and_nested_owner(self):
        index = self.index(
            {
                "demo.py": 'def outer():\n    def inner():\n        return "alpha beta"\n    return "alpha"\n'
            }
        )
        result = locate(index, ["alpha", "beta"], match_all=True)
        self.assertEqual(len(result["candidates"]), 1)
        self.assertEqual(result["candidates"][0]["name"], "outer::inner")

    def test_search_sites_reuse_and_refresh_with_file_content(self):
        index = self.index({"demo.py": 'def f():\n    return "old"\n'})
        next_index = build_index(self.root, adapter_for("auto"), self.root / "cache")
        self.assertEqual(next_index["stats"]["reused_files"], 1)
        self.assertEqual(
            index["files"]["demo.py"]["search_sites"],
            next_index["files"]["demo.py"]["search_sites"],
        )
        (self.root / "demo.py").write_text(
            'def f():\n    return "new"\n', encoding="utf-8"
        )
        refreshed = build_index(self.root, adapter_for("auto"), self.root / "cache")
        self.assertFalse(locate(refreshed, ["old"])["candidates"])
        self.assertTrue(locate(refreshed, ["new"])["candidates"])

    def test_repeated_comment_hits_do_not_inflate_rank(self):
        index = self.index(
            {"demo.py": "def f():\n" + "    # keyword\n" * 25 + "    return 1\n"}
        )
        row = locate(index, ["keyword"])["candidates"][0]
        self.assertEqual(row["score"], 15)
        self.assertEqual(row["omitted_signals"], 13)

    def test_cli_stores_portable_facts_for_context_and_functions(self):
        import contextlib
        import io
        import json
        from reviewkit.cli import main
        from reviewkit.source_identity import verify_source

        self.index(
            {"demo.py": 'TITLE = "业务文字"\ndef run():\n    return "业务文字"\n'}
        )
        out = self.root / "out"
        with contextlib.redirect_stdout(io.StringIO()):
            code = main(
                [
                    "locate",
                    "--repo",
                    str(self.root),
                    "--query",
                    "业务文字",
                    "--out",
                    str(out),
                    "--cache",
                    str(self.root / "cache"),
                ]
            )
        self.assertEqual(code, 0)
        facts = json.loads((out / "facts.json").read_text(encoding="utf-8"))
        self.assertTrue(verify_source(facts))
        result = json.loads((out / "locate.json").read_text(encoding="utf-8"))
        self.assertEqual(len(result["candidates"]), 2)


if __name__ == "__main__":
    unittest.main()
