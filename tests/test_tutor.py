from pathlib import Path
import copy
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / ".deps")]
from reviewkit.engine import extract
from reviewkit.indexer import build_index
from reviewkit.rust import RustAdapter
from reviewkit.storage import write_json
from reviewkit.lecture import accept_new, render_lecture
from reviewkit.tutor import auto_gaps, prepare_step, retell, append_step, step_packet, write_packet, cursor_status, move_cursor


class TutorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        index = build_index(ROOT / "examples/document-pipeline", RustAdapter(), Path(cls.temp.name) / "cache")
        cls.facts = extract(index, [{"symbol": "run"}], 1, 32)
        cls.base = json.loads((ROOT / "examples/document-pipeline/lecture.zh.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.temp_step = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_step.cleanup)
        self.folder = Path(self.temp_step.name)
        self.path = self.folder / "lecture.json"
        self.lecture = copy.deepcopy(self.base)
        write_json(self.path, self.lecture)

    def test_retell_archives_complete_view_atomically_and_rejects_repeat(self):
        before = prepare_step(self.lecture, self.facts, self.lecture["steps"][0])
        result = retell(self.path, self.facts, "s1", {"goal": "new explanation"}, 1, "another example")
        after = json.loads(self.path.read_text(encoding="utf-8"))["steps"][0]
        self.assertEqual(result["r"], 2)
        old = after["earlier"][0]
        for key in ("goal", "show", "gaps", "place", "evidence_hash"):
            self.assertEqual(old[key], before[key])
        with self.assertRaisesRegex(ValueError, "Outdated"):
            retell(self.path, self.facts, "s1", {"goal": "retry"}, 1)
        self.assertEqual(json.loads(self.path.read_text())["steps"][0]["r"], 2)

    def test_invalid_retell_preserves_original_and_releases_lock(self):
        raw = self.path.read_bytes()
        with self.assertRaises(ValueError):
            retell(self.path, self.facts, "s1", {"show": [[1, 9999]]}, 1)
        self.assertEqual(self.path.read_bytes(), raw)
        self.assertFalse(self.path.with_suffix(".json.lock").exists())

    def test_active_lock_is_not_removed(self):
        lock = self.path.with_suffix(".json.lock")
        lock.touch()
        with self.assertRaisesRegex(ValueError, "file lock"):
            retell(self.path, self.facts, "s1", {"goal": "x"}, 1)
        self.assertTrue(lock.exists())

    def test_identity_fields_cannot_be_replaced(self):
        with self.assertRaisesRegex(ValueError, "identity/history"):
            retell(self.path, self.facts, "s1", {"evidence_hash": "new"}, 1)

    def test_gap_complement_uses_other_steps_and_marks_unknown(self):
        step = self.lecture["steps"][0]
        step.pop("gaps", None)
        prepared = prepare_step(self.lecture, self.facts, step)
        self.assertEqual(prepared["gaps"], [{"lines": [65, 69], "label": self.lecture["steps"][2]["short"], "ref": "s3"}])
        step["show"] = [[60, 60]]
        prepared = prepare_step(self.lecture, self.facts, step)
        self.assertTrue(any("待安排" in g["label"] for g in prepared["gaps"]))

    def test_signature_is_derived_and_missing_target_refuses(self):
        step = self.lecture["steps"][0]
        step["stubs"] = [{"node": "src/lib.rs::accept", "ref": "s2"}]
        prepared = prepare_step(self.lecture, self.facts, step)
        target = next(n for n in self.facts["functions"] if n["name"] == "accept")
        self.assertEqual(prepared["stubs"][0]["name"], target["signature"])
        step["stubs"][0]["node"] = "absent"
        with self.assertRaisesRegex(ValueError, "extracted function"):
            prepare_step(self.lecture, self.facts, step)

    def test_packet_is_bounded_reusable_and_full_discussion_is_untouched(self):
        records = [{"lecture": self.lecture["id"], "step": "s1", "r": 1, "quote": "长" * 9000,
                    "question": "q", "answer": "a", "kind": "ask"}]
        original = copy.deepcopy(records)
        packet = step_packet(self.lecture, self.facts, "s1", 3000, records)
        path = self.folder / "packet.json"
        first = write_packet(path, packet)
        second = write_packet(path, packet)
        self.assertLessEqual(path.stat().st_size, 3000)
        self.assertFalse(first["reused"])
        self.assertTrue(second["reused"])
        self.assertEqual(records, original)
        self.assertGreater(packet["omitted_counts"]["discussion"], 0)
        self.assertNotIn("source_snapshot", packet)

    def test_reuse_review_behavior_only_with_matching_evidence(self):
        node = self.lecture["steps"][0]["node"]
        notes = {"cards": {node: {"evidence_hash": self.facts["card_evidence"][node], "input": "existing behavior"}}}
        packet = step_packet(self.lecture, self.facts, "s1", 20000, explanations=notes)
        self.assertEqual(packet["review_behavior"][0]["input"], "existing behavior")
        notes["cards"][node]["evidence_hash"] = "old"
        packet = step_packet(self.lecture, self.facts, "s1", 20000, explanations=notes)
        self.assertTrue(packet["review_behavior_stale"])
        self.assertNotIn("review_behavior", packet)

    def test_archived_code_view_is_independent_of_new_selection(self):
        retell(self.path, self.facts, "s1", {"goal": "focus new lines", "show": [[60, 60]]}, 1)
        lecture = json.loads(self.path.read_text(encoding="utf-8"))
        render_lecture(lecture, self.facts, self.folder / "out.html")
        page = (self.folder / "out.html").read_text(encoding="utf-8")
        self.assertIn('id="s1-r1-L58"', page)
        packet = step_packet(lecture, self.facts, "s1", 20000, revision=1)
        self.assertEqual(packet["code"][0]["line"], 58)

    def test_navigation_resumes_rejects_stale_and_does_not_double_advance(self):
        state = self.folder / "reading.json"
        moved = move_cursor(self.lecture, state, "next", "s1", 1)
        self.assertEqual(moved["current"], "s2")
        self.assertTrue(move_cursor(self.lecture, state, "next", "s1", 1)["reused"])
        self.assertEqual(cursor_status(self.lecture, state)["current"], "s2")
        self.assertTrue(cursor_status(self.lecture, state)["position_only"])
        with self.assertRaisesRegex(ValueError, "Outdated"):
            move_cursor(self.lecture, state, "next", "s2", 99)
        move_cursor(self.lecture, state, "resume", "s3", 1)
        self.assertTrue(move_cursor(self.lecture, state, "next", "s3", 1)["end_of_outline"])
        self.assertTrue(move_cursor(self.lecture, state, "next", "s3", 1)["end_of_outline"])
        other = copy.deepcopy(self.lecture)
        other["source_identity"] = "other source"
        with self.assertRaisesRegex(ValueError, "another lecture/source"):
            cursor_status(other, state)

    def test_planned_step_packet_does_not_need_full_lesson_written(self):
        self.lecture["steps"] = self.lecture["steps"][:1]
        packet = step_packet(self.lecture, self.facts, "s3", 12000)
        self.assertEqual(packet["step"], "s3")
        self.assertTrue(packet["code"])

    def test_new_format_rejects_patch_history_story(self):
        self.lecture["steps"][0]["change"] = {"before": "old code", "after": "new code"}
        with self.assertRaisesRegex(ValueError, "Fixed-source"):
            render_lecture(self.lecture, self.facts, self.folder / "bad.html")

    def test_single_step_append_preserves_existing_views_and_refuses_duplicate(self):
        self.lecture["steps"] = self.lecture["steps"][:1]
        write_json(self.path, self.lecture)
        original = copy.deepcopy(self.lecture["steps"][0])
        draft = self.base["steps"][1]
        append_step(self.path, self.facts, "s2", draft)
        after = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(after["steps"][0], original)
        self.assertEqual(after["steps"][1]["id"], "s2")
        raw = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "already exists"):
            append_step(self.path, self.facts, "s2", draft)
        self.assertEqual(self.path.read_bytes(), raw)

    def test_event_driven_lesson_uses_exact_python_source_without_executing(self):
        from reviewkit.python import PythonAdapter
        index = build_index(ROOT / "examples/document-pipeline", PythonAdapter(), self.folder / "cache")
        facts = extract(index, [{"symbol": "reduce_event", "file": "events.py"}, {"symbol": "view_label", "file": "events.py"}], 0, 32)
        lesson = json.loads((ROOT / "examples/document-pipeline/events-lecture.zh.json").read_text(encoding="utf-8"))
        stats = render_lecture(lesson, facts, self.folder / "events.html")
        self.assertEqual((stats["steps"], stats["stale_steps"], stats["unbound_steps"]), (4, [], []))
        page = (self.folder / "events.html").read_text(encoding="utf-8")
        self.assertIn("程序行为 · 固定源码", page)
        self.assertIn("反事实比较", page)
        self.assertNotIn("行为变化", page)


if __name__ == "__main__":
    unittest.main()
