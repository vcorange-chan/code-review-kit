"""Language routing, evidence identity and source-preserving presentation."""

import contextlib
import io
import json
import re
import copy
from test_reviewkit import RepositoryTestCase
from reviewkit.cli import main
from reviewkit.engine import blank_explanations, validate_explanations
from reviewkit.render import render
from reviewkit.i18n import resolve_language, Translator


class LanguageTests(RepositoryTestCase):
    def test_readme_command_examples_and_sections_match(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        zh = (root / "README.md").read_text(encoding="utf-8")
        en = (root / "README.en.md").read_text(encoding="utf-8")
        self.assertEqual(
            re.findall(r"```[^\n]*\n(.*?)```", zh, re.S),
            re.findall(r"```[^\n]*\n(.*?)```", en, re.S),
        )
        self.assertEqual(len(re.findall(r"^## ", zh, re.M)), len(re.findall(r"^## ", en, re.M)))

    def test_partial_wrong_language_notes_do_not_leak(self):
        self.put("lib.rs", "fn run() {}")
        facts = self.facts()
        notes = blank_explanations(facts)
        notes["cards"][facts["root_ids"][0]]["input"] = "只有输入说明，没有步骤"
        target = self.root / "partial.html"
        self.assertTrue(render(facts, notes, target, output_language="en")["needs_translation"])
        self.assertNotIn("只有输入说明", target.read_text(encoding="utf-8"))

    def call(self, *args):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = main(list(args))
        self.assertEqual(code, 0, stream.getvalue())
        return json.loads(stream.getvalue())

    def command(self, *extra):
        return self.call(
            "function",
            "--repo",
            str(self.repo),
            "--symbol",
            "run",
            "--out",
            str(self.root / "out"),
            "--cache",
            str(self.cache),
            *extra,
        )

    def test_prompt_language_and_explicit_priority(self):
        for prompt, expected in [
            ("请 review run", "zh"),
            ("Review run", "en"),
            ("请用英文输出", "en"),
            ("Review run in Chinese", "zh"),
            ("123", "zh"),
        ]:
            self.assertEqual(resolve_language(prompt=prompt), expected)
        self.assertEqual(resolve_language("en", "请用中文输出"), "en")
        self.assertEqual(resolve_language("中文", "Review run"), "zh")
        with self.assertRaises(ValueError):
            resolve_language("fr")

    def test_english_static_ui_is_complete_and_source_remains_original(self):
        self.put("lib.rs", 'fn run() { let text = "功能实现 · 错误输出 · 中文源码"; }')
        facts = self.facts()
        facts["output_language"] = "en"
        before = copy.deepcopy(facts)
        notes = blank_explanations(facts)
        target = self.root / "en.html"
        stats = render(facts, notes, target)
        html = target.read_text(encoding="utf-8")
        self.assertIn('<html lang="en">', html)
        self.assertIn("Implementation", html)
        self.assertIn("Code locations and source", html)
        self.assertIn("功能实现 · 错误输出 · 中文源码", html)
        # Source snippets and code are the only allowed Chinese content here.
        visible = re.sub(r"<pre[^>]*>.*?</pre>", "", html, flags=re.S)
        self.assertFalse(re.search("[\u3400-\u9fff]", visible), visible[-1000:])
        self.assertEqual(facts, before)
        self.assertEqual(stats["output_language"], "en")

    def test_switch_invalidates_html_cache_and_keeps_legacy_notes(self):
        self.put("lib.rs", "fn run() {}")
        zh = self.command("--prompt", "请审阅 run")
        old = (self.root / "out/explanations.json").read_bytes()
        en = self.command("--prompt", "Review run")
        self.assertFalse(en["html_reused"])
        self.assertEqual(en["output_language"], "en")
        self.assertEqual((self.root / "out/explanations.json").read_bytes(), old)
        self.assertEqual(
            json.loads((self.root / "out/explanations.seed.json").read_text(encoding="utf-8"))[
                "output_language"
            ],
            "en",
        )
        self.assertEqual(
            json.loads((self.root / "out/evidence-packet.json").read_text(encoding="utf-8"))[
                "output_language"
            ],
            "en",
        )
        again = self.command("--prompt", "Review run")
        self.assertTrue(again["html_reused"])
        self.assertEqual(zh["output_language"], "zh")

    def test_wrong_language_explanation_is_requested_not_mixed_or_rebound(self):
        self.put("lib.rs", "fn run() {}")
        facts = self.facts()
        notes = blank_explanations(facts)
        notes["cards"][facts["root_ids"][0]]["steps"] = [
            {"title": "旧中文解释", "detail": "不能伪装成英文解释。"}
        ]
        original = copy.deepcopy(notes)
        target = self.root / "en.html"
        stats = render(facts, notes, target, output_language="en")
        self.assertTrue(stats["needs_translation"])
        self.assertEqual(stats["explained"], 0)
        self.assertNotIn("旧中文解释", target.read_text(encoding="utf-8"))
        self.assertEqual(notes, original)

    def test_english_prose_preserves_evidence_and_escaping(self):
        self.put("lib.rs", "fn run() {}")
        facts = self.facts()
        notes = blank_explanations(facts)
        notes["output_language"] = "en"
        notes["cards"][facts["root_ids"][0]].update(
            title="Read source",
            steps=[{"title": "Inspect input", "detail": "<script>unsafe()</script>"}],
        )
        target = self.root / "en.html"
        stats = render(facts, notes, target)
        self.assertTrue(validate_explanations(notes, facts)[facts["root_ids"][0]])
        self.assertEqual(stats["explained"], 1)
        self.assertIn("&lt;script&gt;unsafe()", target.read_text(encoding="utf-8"))

    def test_render_and_packet_entries_use_same_language_routing(self):
        self.put("lib.rs", "fn run() {}")
        self.command()
        folder = self.root / "out"
        report = self.call(
            "render",
            "--facts",
            str(folder / "facts.json"),
            "--explanations",
            str(folder / "explanations.json"),
            "--html",
            str(folder / "english.html"),
            "--prompt",
            "Review run",
        )
        self.assertEqual(report["output_language"], "en")
        self.call(
            "packet",
            "--facts",
            str(folder / "facts.json"),
            "--out",
            str(folder / "english-packet.json"),
            "--prompt",
            "Review run",
        )
        self.assertEqual(
            json.loads((folder / "english-packet.json").read_text(encoding="utf-8"))[
                "output_language"
            ],
            "en",
        )
