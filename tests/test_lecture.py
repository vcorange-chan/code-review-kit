from pathlib import Path
import copy
import json
import sys
import tempfile
import unittest

HOME = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(HOME), str(HOME / ".deps")]
from reviewkit.indexer import build_index
from reviewkit.rust import RustAdapter
from reviewkit.engine import extract
from reviewkit.lecture import accept_new, discuss, render_lecture

EXAMPLE = HOME / "examples/document-pipeline"


class LectureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        index = build_index(EXAMPLE, RustAdapter(), Path(cls.temp.name) / "cache")
        cls.facts = extract(index, [{"symbol": "run"}], depth=1, max_nodes=32)
        cls.base = json.loads((EXAMPLE / "lecture.zh.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.lecture = copy.deepcopy(self.base)
        self.out = Path(self.temp.name) / "out.html"
        self.log = Path(self.temp.name) / (self.id().rsplit(".", 1)[-1] + ".jsonl")

    def render(self, **kwargs):
        stats = render_lecture(self.lecture, self.facts, self.out, **kwargs)
        return stats, self.out.read_text(encoding="utf-8")

    def test_public_example_is_bound_and_current(self):
        stats, page = self.render()
        self.assertEqual(stats["steps"], 3)
        self.assertEqual(stats["stale_steps"] + stats["unbound_steps"], [])
        self.assertIn("let value = accept(&amp;value)?;", page)
        self.assertNotIn('class="discussion"', page)

    def test_every_line_needs_a_place(self):
        self.lecture["steps"][0]["gaps"] = []
        with self.assertRaisesRegex(ValueError, "未覆盖"):
            self.render()

    def test_decision_must_be_visible(self):
        self.lecture["steps"][0]["decisions"][0]["line"] = 66
        with self.assertRaisesRegex(ValueError, "折叠段"):
            self.render()

    def test_reasons_need_kind_and_support(self):
        self.lecture["steps"][0]["reasons"][0]["kind"] = "倒推"
        with self.assertRaisesRegex(ValueError, "kind"):
            self.render()
        self.lecture["steps"][0]["reasons"][0] = {"kind": "inferred", "text": "x"}
        with self.assertRaisesRegex(ValueError, "support"):
            self.render()

    def test_changed_source_marks_step_for_review(self):
        self.lecture["steps"][1]["evidence_hash"] = "0" * 64
        stats, page = self.render()
        self.assertEqual(stats["stale_steps"], ["s2"])
        self.assertIn("讲解待复核", page)

    def test_accept_new_never_rebinds(self):
        self.lecture["steps"][0]["evidence_hash"] = "0" * 64
        del self.lecture["steps"][1]["evidence_hash"]
        self.assertEqual(accept_new(self.lecture, self.facts), ["s2"])
        self.assertEqual(self.lecture["steps"][0]["evidence_hash"], "0" * 64)

    def test_missing_node_is_reported(self):
        self.lecture["steps"][0]["node"] = "src/lib.rs::absent"
        with self.assertRaisesRegex(ValueError, "absent"):
            self.render()

    def test_adjacent_out_of_scope_gaps_collapse(self):
        step = self.lecture["steps"][2]
        step["gaps"][1:] = [
            {"lines": [70, 72], "label": "a", "out": True},
            {"lines": [73, 75], "label": "b", "out": True},
        ]
        _, page = self.render()
        self.assertIn("本课程不涉及（2 段）", page)

    def test_discussion_keeps_revision_and_unmatched_records(self):
        discuss(self.lecture, self.log, "s3", "ask", "unwrap_or", "为什么?", "因为可选。")
        step = self.lecture["steps"][2]
        step["earlier"] = [{"r": 1, **{k: step[k] for k in ["goal", "reasons", "method", "decisions", "change"]}}]
        step["r"] = 2
        discuss(self.lecture, self.log, "s3", "note", "", text="当前修订的旁注")
        with self.assertRaisesRegex(ValueError, "1–2"):
            discuss(self.lecture, self.log, "s3", "note", "", text="x", revision=3)
        with self.log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"lecture": self.lecture["id"], "step": "s9", "r": 1, "kind": "note", "text": "旧"}, ensure_ascii=False) + "\n")
            handle.write(json.dumps({"lecture": "other", "step": "s1", "r": 1, "kind": "note", "text": "他人"}, ensure_ascii=False) + "\n")
        stats, page = self.render(discussion_path=self.log)
        self.assertEqual((stats["discussion_records"], stats["unmatched_discussion"], stats["other_lecture_records"]), (3, 1, 1))
        self.assertIn("针对第 1 次讲解", page)
        self.assertIn("提问 1 · 旁注 1", page)
        self.assertIn("未匹配的讨论", page)
        self.assertNotIn("他人", page)

    def test_english_labels(self):
        stats, page = self.render(output_language="en")
        self.assertEqual(stats["output_language"], "en")
        self.assertIn("Step 1 / 3", page)
        self.assertIn("Why this design", page)
        self.assertIn('"Step goal: "', page)


if __name__ == "__main__":
    unittest.main()
