"""Regression cases from the external review; no target application execution."""

from test_reviewkit import RepositoryTestCase
from reviewkit.engine import extract, blank_explanations, validate_explanations
from reviewkit.business import extract_business, pin_sources
from reviewkit.render import render
from reviewkit.source_links import SourceLinks


class ReviewFixTests(RepositoryTestCase):
    def test_annotated_parameter_generic_method_is_followed(self):
        self.put(
            "lib.rs",
            "struct Parser; impl Parser { fn parse<T>(&self) {} } fn run(parser: &Parser) { parser.parse::<u8>(); }",
        )
        edge = next(e for e in self.facts()["edges"] if e["name"] == "parse")
        self.assertEqual(edge["receiver"], "parser")
        self.assertEqual(edge["basis"], "annotated_parameter_type")
        self.assertEqual(len(edge["candidates"]), 1)

    def test_annotated_parameter_method_is_followed(self):
        self.put(
            "lib.rs",
            "struct Parser; impl Parser { fn parse(&self) {} } fn run(parser: &Parser) { parser.parse(); }",
        )
        facts = self.facts()
        edge = next(e for e in facts["edges"] if e["name"] == "parse")
        self.assertEqual(edge["basis"], "annotated_parameter_type")
        self.assertEqual(len(edge["candidates"]), 1)
        self.assertTrue(any(f["name"] == "parse" for f in facts["functions"]))

    def test_unknown_receiver_is_reported_instead_of_disappearing(self):
        self.put("lib.rs", "fn run() { let client = make_client(); client.send(); }")
        edge = next(e for e in self.facts()["edges"] if e["name"] == "send")
        self.assertEqual(edge["status"], "unresolved")
        self.assertEqual(edge["reason"], "unknown_receiver_type")

    def test_shadowed_parameter_is_not_falsely_resolved(self):
        self.put(
            "lib.rs",
            "struct Parser; impl Parser { fn parse(&self) {} } fn run(parser: &Parser) { let parser = other(); parser.parse(); }",
        )
        edge = next(e for e in self.facts()["edges"] if e["name"] == "parse")
        self.assertEqual(edge["reason"], "receiver_binding_may_be_shadowed")
        self.assertEqual(edge["candidates"], [])

    def test_generic_and_dyn_receivers_remain_unresolved(self):
        self.put(
            "lib.rs",
            "fn run<T: Trait>(generic: &T, dynamic: &dyn Trait) { generic.send(); dynamic.send(); }",
        )
        edges = [e for e in self.facts()["edges"] if e["name"] == "send"]
        self.assertEqual(
            [e["reason"] for e in edges], ["polymorphic_receiver", "polymorphic_receiver"]
        )

    def test_unrelated_derive_does_not_invalidate_function(self):
        self.put("lib.rs", "struct Unrelated; fn run() {}")
        old = self.facts()
        notes = blank_explanations(old)
        self.put("lib.rs", "#[derive(Debug)]\nstruct Unrelated; fn run() {}")
        self.assertTrue(validate_explanations(notes, self.facts())[old["root_ids"][0]])

    def test_own_attribute_still_invalidates_function(self):
        self.put("lib.rs", "fn run() {}")
        old = self.facts()
        notes = blank_explanations(old)
        self.put("lib.rs", "#[inline]\nfn run() {}")
        self.assertFalse(validate_explanations(notes, self.facts())[old["root_ids"][0]])

    def test_related_type_derive_still_invalidates_function(self):
        self.put("lib.rs", "struct Parser; fn run(parser: &Parser) {}")
        old = self.facts()
        notes = blank_explanations(old)
        self.put("lib.rs", "#[derive(Debug)]\nstruct Parser; fn run(parser: &Parser) {}")
        self.assertFalse(validate_explanations(notes, self.facts())[old["root_ids"][0]])

    def test_symbol_business_anchor_survives_lines_inserted_above(self):
        self.put("lib.rs", "fn before() {}\nfn run() {}")
        manifest = {"nodes": [{"id": "read", "sources": [{"file": "lib.rs", "symbol": "run"}]}]}
        old = extract_business(self.index(), manifest, 0, 16)
        notes = blank_explanations(old)
        self.put("lib.rs", "\n\n\nfn before() {}\nfn run() {}")
        fresh = extract_business(self.index(), manifest, 0, 16)
        self.assertEqual(fresh["functions"][-1]["sources"][0]["line"], 5)
        self.assertTrue(validate_explanations(notes, fresh)["business::read"])

    def test_pin_sources_is_explicit_and_keeps_context_ranges(self):
        self.put("lib.rs", "fn run() {}")
        self.put("screen.dart", "void view() {}")
        old = {
            "nodes": [
                {
                    "id": "x",
                    "sources": [{"file": "lib.rs", "line": 1}, {"file": "screen.dart", "line": 1}],
                }
            ]
        }
        pinned, count = pin_sources(self.index(), old)
        self.assertEqual(count, 1)
        self.assertEqual(pinned["nodes"][0]["sources"][0]["symbol"], "lib.rs::run")
        self.assertIn("line", old["nodes"][0]["sources"][0])
        self.assertIn("line", pinned["nodes"][0]["sources"][1])

    def test_default_report_is_self_contained_without_host_paths(self):
        self.put("lib.rs", "fn run() {}")
        facts = self.facts()
        notes = blank_explanations(facts)
        output = self.root / "review.html"
        render(facts, notes, output)
        text = output.read_text(encoding="utf-8")
        self.assertNotIn(str(self.repo), text)
        self.assertNotIn(self.repo.as_uri(), text)
        self.assertNotIn("file://", text)
        self.assertIn('id="source-view"', text)
        import re

        targets = re.findall(r'data-snapshot="([^"]+)"', text)
        self.assertTrue(targets)
        self.assertTrue(all('id="' + target + '"' in text for target in targets))

    def test_remote_link_template_escapes_paths_and_uses_current_lines(self):
        self.put("src/a b.rs", "fn run() {}")
        facts = self.facts()
        links = SourceLinks(
            facts,
            self.root / "review.html",
            template="https://example.invalid/blob/main/{path}#L{line}",
        )
        value = links.reference("src/a b.rs", 7)
        self.assertIn("https://example.invalid/blob/main/src/a%20b.rs#L7", value)
        self.assertNotIn(str(self.repo), value)
        with self.assertRaises(ValueError):
            SourceLinks(facts, self.root / "x", template="javascript:alert({line})")

    def test_relative_and_local_links_are_explicit_modes(self):
        self.put("lib.rs", "fn run() {}")
        facts = self.facts()
        relative = SourceLinks(facts, self.root / "review.html", mode="relative").reference(
            "lib.rs", 1
        )
        self.assertIn('href="repo/lib.rs"', relative)
        local = SourceLinks(facts, self.root / "review.html", mode="local").reference("lib.rs", 1)
        self.assertIn("file://", local)

    def test_ambiguous_method_candidates_do_not_expand(self):
        self.put(
            "lib.rs",
            "struct Parser; impl A for Parser { fn parse(&self) {} } impl B for Parser { fn parse(&self) {} } fn run(parser: &Parser) { parser.parse(); }",
        )
        facts = self.facts()
        edge = next(e for e in facts["edges"] if e["name"] == "parse")
        self.assertEqual(edge["status"], "ambiguous")
        self.assertEqual(len(facts["functions"]), 1)

    def test_qualified_external_type_is_not_matched_to_local_type(self):
        self.put(
            "lib.rs",
            "struct Parser; impl Parser { fn parse(&self) {} } fn run(parser: &external::Parser) { parser.parse(); }",
        )
        edge = next(e for e in self.facts()["edges"] if e["name"] == "parse")
        self.assertEqual(edge["reason"], "qualified_receiver_requires_semantic_resolution")
        self.assertEqual(edge["candidates"], [])

    def test_parameter_does_not_bind_same_name_from_another_module(self):
        self.put(
            "lib.rs",
            "mod unrelated { struct Parser; impl Parser { fn parse(&self) {} } } fn run(parser: &Parser) { parser.parse(); }",
        )
        edge = next(e for e in self.facts()["edges"] if e["name"] == "parse")
        self.assertEqual(edge["candidates"], [])

    def test_cfg_on_visible_import_still_invalidates(self):
        self.put("lib.rs", '#[cfg(feature="a")]\nuse a::Trait; fn run() {}')
        old = self.facts()
        notes = blank_explanations(old)
        self.put("lib.rs", '#[cfg(feature="b")]\nuse a::Trait; fn run() {}')
        self.assertFalse(validate_explanations(notes, self.facts())[old["root_ids"][0]])

    def test_type_used_by_constructor_is_tracked(self):
        self.put("lib.rs", "struct Parser; fn run() { Parser::new(); }")
        old = self.facts()
        notes = blank_explanations(old)
        self.put("lib.rs", "#[derive(Debug)]\nstruct Parser; fn run() { Parser::new(); }")
        self.assertFalse(validate_explanations(notes, self.facts())[old["root_ids"][0]])
