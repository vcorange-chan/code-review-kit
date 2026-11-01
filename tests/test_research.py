import copy
import io
import json
from pathlib import Path
import tempfile
import sys
import unittest
from contextlib import redirect_stdout

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / ".deps")]

from reviewkit.cli import main
from reviewkit.dossier import build_dossier
from reviewkit.evidence import byte_size, evidence, page, verify
from reviewkit import investigation
from reviewkit.engine import extract
from reviewkit.indexer import build_index
from reviewkit.languages import adapter_for
from reviewkit.research_render import render_research
from reviewkit.source_identity import capture_source
from reviewkit.storage import read_json, write_json


class EvidenceTests(unittest.TestCase):
    def test_content_addressed_and_tamper_refused(self):
        a = evidence("test", {"source_identity": "abc"}, [{"text": "中文"}])
        self.assertEqual(
            a, evidence("test", {"source_identity": "abc"}, [{"text": "中文"}])
        )
        verify(a)
        changed = copy.deepcopy(a)
        changed["data"][0]["text"] = "changed"
        with self.assertRaisesRegex(ValueError, "hash"):
            verify(changed)

    def test_pages_are_utf8_bounded_contiguous_and_oversize_explicit(self):
        item = evidence("test", {}, [{"text": "中" * 250, "n": i} for i in range(8)])
        rows, offset = [], 0
        while True:
            result = page(item, offset, 2, 2048)
            self.assertLessEqual(byte_size(result), 2048)
            rows.extend(result["rows"])
            if result["next_offset"] is None:
                break
            self.assertGreater(result["next_offset"], offset)
            offset = result["next_offset"]
        self.assertEqual(rows, item["data"])
        result = page(evidence("large", {}, ["x" * 4000]), budget=2048)
        self.assertEqual(result["next_offset"], 0)
        self.assertEqual(result["oversized_row"]["offset"], 0)
        self.assertEqual(result["rows"], [])


class InvestigationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ev = evidence("source", {"source_identity": "snapshot-a"}, [{"line": 7}])
        investigation.import_evidence(self.root, [self.ev])

    def test_history_preserves_original_and_stale_revision_refused(self):
        investigation.append(
            self.root,
            {"id": "u1", "kind": "unknown", "text": "where does it start?"},
            0,
        )
        with self.assertRaisesRegex(ValueError, "revision"):
            investigation.append(self.root, {"kind": "note", "text": "stale"}, 0)
        investigation.append(
            self.root,
            {
                "id": "u1",
                "kind": "unknown",
                "text": "entry located",
                "status": "resolved",
                "resolution": "at the selected function",
                "support": [self.ev["id"]],
            },
            1,
        )
        state = investigation.snapshot(self.root)
        self.assertEqual(state["records"][0]["status"], "resolved")
        self.assertEqual(state["history"][0]["record"]["text"], "where does it start?")
        self.assertEqual(state["revision"], 2)

    def test_resolution_hypothesis_and_finding_need_corresponding_evidence(self):
        for row in [
            {"kind": "finding", "text": "guess"},
            {
                "kind": "unknown",
                "status": "resolved",
                "text": "done",
                "support": [self.ev["id"]],
            },
            {
                "kind": "unknown",
                "status": "contradicted",
                "text": "no",
                "resolution": "because",
                "support": [self.ev["id"]],
            },
            {
                "kind": "hypothesis",
                "status": "refuted",
                "text": "no",
                "support": [self.ev["id"]],
            },
        ]:
            with self.subTest(row=row), self.assertRaises(ValueError):
                investigation.append(self.root, row, 0)
        investigation.append(
            self.root,
            {
                "kind": "hypothesis",
                "status": "refuted",
                "text": "counterexample",
                "counter": [self.ev["id"]],
            },
            0,
        )

    def test_tampered_history_or_evidence_refuses_snapshot(self):
        investigation.append(
            self.root,
            {"kind": "finding", "text": "found", "support": [self.ev["id"]]},
            0,
        )
        path = self.root / "history.jsonl"
        original = path.read_text(encoding="utf-8")
        path.write_text(original.replace('"found"', '"tampered"'), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "chain"):
            investigation.snapshot(self.root)
        path.write_text(original, encoding="utf-8")
        path = self.root / "evidence" / (self.ev["id"] + ".json")
        row = read_json(path)
        row["data"] = []
        write_json(path, row)
        with self.assertRaisesRegex(ValueError, "hash"):
            investigation.snapshot(self.root)

    def test_crash_fragment_refused_without_modifying_original(self):
        investigation.append(self.root, {"kind": "note", "text": "original"}, 0)
        path = self.root / "history.jsonl"
        path.write_text(path.read_text(encoding="utf-8").rstrip("\n"), encoding="utf-8")
        raw = path.read_bytes()
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            investigation.append(self.root, {"kind": "note", "text": "next"}, 1)
        self.assertEqual(path.read_bytes(), raw)

    def test_mixed_sources_are_visible_and_paths_rejected(self):
        other = evidence("source", {"source_identity": "snapshot-b"}, [])
        investigation.import_evidence(self.root, [other])
        investigation.append(
            self.root,
            {
                "kind": "note",
                "text": "compare",
                "support": [self.ev["id"], other["id"]],
            },
            0,
        )
        self.assertTrue(investigation.snapshot(self.root)["mixed_sources"])
        with self.assertRaises(ValueError):
            investigation.load_evidence(self.root, "../../secret")
        (self.root / ".write.lock").write_text("another writer", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "locked"):
            investigation.append(self.root, {"kind": "note", "text": "x"}, 1)


class DossierTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        (self.repo / "main.py").write_text(
            'def helper(x):\n    return x\n\ndef start(item):\n    if not item:\n        raise ValueError("bad")\n    return helper(item)\n',
            encoding="utf-8",
        )
        index = build_index(self.repo, adapter_for("python"), self.repo / "cache")
        self.facts = extract(index, [{"symbol": "start"}])
        capture_source(self.facts, self.repo, adapter=index["adapter"])

    def test_facet_scope_call_uncertainty_and_source_do_not_reread(self):
        (self.repo / "main.py").write_text("changed", encoding="utf-8")
        dossier, bundle = build_dossier(self.facts, "start")
        by = {e["operation"]: e for e in bundle}
        self.assertEqual(
            by["function.source"]["data"][0], {"line": 4, "text": "def start(item):"}
        )
        self.assertEqual(dossier["facets"]["branches"]["count"], 1)
        self.assertIn("implicit", " ".join(by["function.errors"]["limits"]))
        self.assertEqual(len(by["function.calls"]["data"]), 2)
        self.assertTrue(
            any(e["status"] == "unresolved" for e in by["function.calls"]["data"])
        )
        self.assertEqual(len(by["function.source"]["data"]), 4)

    def test_bad_source_and_ambiguous_symbol_refused(self):
        changed = copy.deepcopy(self.facts)
        changed["functions"][0]["source"] = "fake"
        with self.assertRaises(ValueError):
            build_dossier(changed, "start")
        duplicate = copy.deepcopy(self.facts)
        duplicate["functions"].append(
            dict(duplicate["functions"][0], id="other.py::start")
        )
        duplicate.pop("source_snapshot")
        with self.assertRaises(ValueError):
            build_dossier(duplicate, "start")

    def test_html_escaped_bilingual_private_opt_in_and_history_retained(self):
        dossier, bundle = build_dossier(self.facts, "start")
        session = self.repo / "session"
        investigation.append(
            session,
            {"kind": "note", "text": "PRIVATE <script>alert(1)</script> {{title}}"},
            0,
        )
        for lang, title in [("zh", "函数档案"), ("en", "Function dossiers")]:
            path = self.repo / (lang + ".html")
            render_research(
                path, self.facts, dossiers=[dossier], evidence=bundle, language=lang
            )
            html = path.read_text(encoding="utf-8")
            self.assertIn(title, html)
            self.assertNotIn(str(self.repo), html)
            self.assertNotIn("PRIVATE", html)
            render_research(
                path,
                self.facts,
                dossiers=[dossier],
                evidence=bundle,
                investigation=investigation.snapshot(session),
                language=lang,
            )
            html = path.read_text(encoding="utf-8")
            self.assertIn("PRIVATE &lt;script&gt;", html)
            self.assertIn("{{title}}", html)
            self.assertIn('"revision": 1', html.replace("&quot;", '"'))

    def test_cli_end_to_end_locate_dossier_investigation(self):
        out = self.repo / "report"

        def run(argv):
            stream = io.StringIO()
            with redirect_stdout(stream):
                code = main(argv)
            self.assertEqual(code, 0, stream.getvalue())
            return json.loads(stream.getvalue())

        found = run(
            [
                "locate",
                "--repo",
                str(self.repo),
                "--query",
                "bad",
                "--out",
                str(out),
                "--cache",
                str(self.repo / "cache"),
            ]
        )
        self.assertTrue(Path(found["html"]).exists())
        packet = run(
            [
                "dossier",
                "--facts",
                str(out / "facts.json"),
                "--symbol",
                "start",
                "--out",
                str(out / "fn"),
                "--facet",
                "errors",
                "--bytes",
                "2048",
            ]
        )
        self.assertEqual(packet["operation"], "function.errors")
        session = str(self.repo / "session")
        run(
            [
                "investigate",
                "import",
                "--session",
                session,
                "--input",
                str(out / "evidence.json"),
            ]
        )
        record = self.repo / "note.json"
        write_json(
            record,
            {
                "kind": "finding",
                "text": "rejects empty input",
                "support": [packet["id"]],
            },
        )
        run(
            [
                "investigate",
                "record",
                "--session",
                session,
                "--input",
                str(record),
                "--expected-revision",
                "0",
            ]
        )
        state = run(["investigate", "show", "--session", session])
        self.assertEqual(state["rows"][0]["text"], "rejects empty input")
        run(
            [
                "investigate",
                "render",
                "--session",
                session,
                "--out",
                str(out / "journal.html"),
                "--facts",
                str(out / "facts.json"),
                "--lookup",
                str(out / "locate.json"),
            ]
        )


if __name__ == "__main__":
    unittest.main()
