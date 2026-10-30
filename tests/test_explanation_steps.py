from test_reviewkit import RepositoryTestCase
from reviewkit.engine import blank_explanations, validate_explanations
from reviewkit.business import extract_business
from reviewkit.render import render
from reviewkit.explanation_steps import step_location
from reviewkit.source_links import SourceLinks


class ExplanationStepTests(RepositoryTestCase):
    def make_notes(self):
        self.put("lib.rs", "fn run() {\n    helper();\n}\nfn helper() {}")
        facts = self.facts()
        notes = blank_explanations(facts)
        notes["cards"][facts["root_ids"][0]]["steps"] = [
            {
                "title": "Call helper",
                "detail": "Pass control to helper, then continue after its return.",
                "actor": "run",
                "input": "No arguments",
                "result": "Helper completed",
                "next": "Return from run",
                "offset": 1,
                "end_offset": 1,
            }
        ]
        return facts, notes

    def test_block_link_points_inside_function_and_moves_with_it(self):
        facts, notes = self.make_notes()
        ident = facts["root_ids"][0]
        step = notes["cards"][ident]["steps"][0]
        functions = {f["id"]: f for f in facts["functions"]}
        self.assertEqual(step_location(step, ident, functions)["line"], 2)
        self.put("lib.rs", "\n\nfn run() {\n    helper();\n}\nfn helper() {}")
        fresh = self.facts()
        self.assertTrue(validate_explanations(notes, fresh)[ident])
        self.assertEqual(
            step_location(step, ident, {f["id"]: f for f in fresh["functions"]})["line"], 4
        )

    def test_invalid_block_ranges_and_unknown_refs_are_rejected(self):
        facts, notes = self.make_notes()
        step = notes["cards"][facts["root_ids"][0]]["steps"][0]
        for key, value in [
            ("offset", -1),
            ("end_offset", 99),
            ("offset", True),
            ("reference", "unknown"),
            ("source_index", 0),
        ]:
            with self.subTest(key=key, value=value):
                original = step.copy()
                step[key] = value
                with self.assertRaises(ValueError):
                    validate_explanations(notes, facts)
                step.clear()
                step.update(original)

    def test_rich_steps_are_readable_and_escaped_in_both_languages(self):
        facts, notes = self.make_notes()
        step = notes["cards"][facts["root_ids"][0]]["steps"][0]
        step["actor"] = "<script>actor</script>"
        target = self.root / "review.html"
        notes["output_language"] = "en"
        render(facts, notes, target, output_language="en")
        html = target.read_text(encoding="utf-8")
        self.assertIn("<details open data-linear-step><summary>01 · Call helper", html)
        self.assertIn("Executed by", html)
        self.assertIn("&lt;script&gt;actor", html)
        self.assertIn('data-snapshot="' + SourceLinks.target("lib.rs", 2) + '"', html)
        notes["output_language"] = "zh"
        render(facts, notes, target, output_language="zh")
        self.assertIn("进入此步", target.read_text(encoding="utf-8"))

    def test_business_step_can_cite_a_second_selected_source(self):
        self.put("lib.rs", "fn run() {}")
        self.put("context.txt", "first\nsecond\nthird")
        manifest = {
            "nodes": [
                {
                    "id": "read",
                    "sources": [
                        {"file": "lib.rs", "symbol": "run"},
                        {"file": "context.txt", "line": 1, "end_line": 3},
                    ],
                }
            ]
        }
        facts = extract_business(self.index(), manifest, 0, 16)
        notes = blank_explanations(facts)
        step = {
            "title": "Second file",
            "detail": "The caller uses data from this block.",
            "source_index": 1,
            "offset": 1,
            "end_offset": 2,
        }
        notes["cards"]["business::read"]["steps"] = [step]
        validate_explanations(notes, facts)
        location = step_location(step, "business::read", {f["id"]: f for f in facts["functions"]})
        self.assertEqual(location, {"file": "context.txt", "line": 2, "end_line": 3})

    def test_bad_actor_is_rejected_but_legacy_steps_still_work(self):
        facts, notes = self.make_notes()
        step = notes["cards"][facts["root_ids"][0]]["steps"][0]
        step["actor"] = ["bad"]
        with self.assertRaises(ValueError):
            validate_explanations(notes, facts)
        notes["cards"][facts["root_ids"][0]]["steps"] = [
            {"title": "Legacy step", "detail": "Existing explanations remain valid."}
        ]
        validate_explanations(notes, facts)
