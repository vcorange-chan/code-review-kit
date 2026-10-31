"""Source viewers must map original text, never a compact declaration summary."""

import json
from test_reviewkit import RepositoryTestCase
from reviewkit.engine import extract, make_packet
from reviewkit.languages import adapter_for
from reviewkit.indexer import build_index
from reviewkit.source_links import SourceLinks


class SourceSnapshotTests(RepositoryTestCase):
    def python_facts(self):
        self.put(
            "flow.py",
            """class Worker:
    limit: int = 3

    def parse(self):
        value = "BODY_ONLY_SENTINEL"
        return value

    def resolve_call(self):
        return 2

def run(worker: Worker) -> Worker:
    return worker
""",
        )
        index = build_index(self.repo, adapter_for("python"), self.cache)
        return extract(index, [{"symbol": "run"}], depth=0)

    def test_python_class_summary_cannot_overwrite_original_lines(self):
        facts = self.python_facts()
        item = facts["types"][0]
        self.assertNotEqual(item["text"], item["source"])
        links = SourceLinks(facts, self.root / "review.html")
        actual = (self.repo / "flow.py").read_text().splitlines()
        self.assertGreater(len(links.lines["flow.py"]), 5)
        for number, text in links.lines["flow.py"].items():
            self.assertEqual(text, actual[number - 1], f"flow.py:{number}")

    def test_dart_class_and_rust_type_snapshots_are_verbatim(self):
        samples = [
            (
                "dart",
                "flow.dart",
                "class Worker {\n int parse() {\n return 1;\n }\n int other() => 2;\n}\nWorker run(Worker worker) => worker;",
            ),
            (
                "rust",
                "flow.rs",
                "struct Worker {\n limit: u32,\n}\nfn run(worker: Worker) -> Worker { worker }",
            ),
        ]
        for language, name, code in samples:
            with self.subTest(language=language):
                self.put(name, code)
                index = build_index(self.repo, adapter_for(language), self.cache)
                facts = extract(index, [{"symbol": "run"}], depth=0)
                self.assertTrue(facts["types"])
                links = SourceLinks(facts, self.root / (language + ".html"))
                for number, text in links.lines[name].items():
                    self.assertEqual(text, code.splitlines()[number - 1])

    def test_rendering_snapshot_does_not_replace_it_with_current_file_contents(self):
        facts = self.python_facts()
        self.put("flow.py", "# changed after extraction\n")
        links = SourceLinks(facts, self.root / "review.html")
        self.assertEqual(links.lines["flow.py"][1], "class Worker:")

    def test_legacy_type_summary_is_not_invented_as_source(self):
        facts = self.python_facts()
        item = facts["types"][0]
        item.pop("source", None)
        links = SourceLinks(facts, self.root / "review.html")
        self.assertNotIn(item["line"], links.lines[item["file"]])
        links.item(item)
        self.assertIn("未纳入源码快照", links.lines[item["file"]][item["line"]])

    def test_conflicting_verbatim_sources_are_rejected_instead_of_overwritten(self):
        links = SourceLinks(self.python_facts(), self.root / "review.html")
        with self.assertRaisesRegex(ValueError, "Conflicting source"):
            links.add("flow.py", 1, "def unrelated():")
        self.assertEqual(links.lines["flow.py"][1], "class Worker:")

    def test_raw_type_source_is_kept_out_of_bounded_model_packet(self):
        facts = self.python_facts()
        self.assertIn("BODY_ONLY_SENTINEL", facts["types"][0]["source"])
        packet = make_packet(facts, 24000)
        self.assertTrue(packet["types"])
        self.assertNotIn("source", packet["types"][0])
        self.assertNotIn("BODY_ONLY_SENTINEL", json.dumps(packet))
