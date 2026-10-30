"""Observable extraction, conservative dispatch and mixed-language evidence behavior."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from test_reviewkit import HOME
from reviewkit.languages import adapter_for
from reviewkit.indexer import build_index
from reviewkit.engine import extract, choose, blank_explanations, validate_explanations
from reviewkit.business import extract_business
from reviewkit.cli import main


class LanguageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.cache = self.root / "cache"

    def tearDown(self):
        self.temp.cleanup()

    def put(self, file, text):
        path = self.repo / file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def facts(self, symbol="run", language="auto", file=None):
        index = build_index(self.repo, adapter_for(language), self.cache)
        return extract(index, [{"symbol": symbol, "file": file}], 2)

    def test_python_async_exceptions_and_nested_scope_boundaries(self):
        self.put(
            "flow.py",
            """async def run(client, text: str) -> str:
    if not text:
        raise ValueError("empty")
    try:
        result = await client.send(text)
    except TimeoutError:
        return "fallback"
    finally:
        close()
    def hidden():
        hidden_call()
        return "nested"
    callback = lambda: lambda_call()
    return result
""",
        )
        facts = self.facts()
        fn = choose(facts["functions"], "run")
        self.assertTrue(fn["async"])
        self.assertEqual(
            [c["name"] for c in fn["calls"]], ["ValueError", "client.send", "close"]
        )
        self.assertEqual(len(fn["returns"]), 2)
        self.assertEqual(fn["errors"][0]["variant"], 'ValueError("empty")')
        self.assertTrue(
            any(
                "TimeoutError" in b["arms"] and "finally" in b["arms"]
                for b in fn["branches"]
            )
        )
        self.assertTrue(
            any(
                e["name"] == "client.send" and e["status"] == "unresolved"
                for e in facts["edges"]
            )
        )

    def test_python_import_alias_follows_only_explicit_local_module(self):
        self.put(
            "flow.py", "from helper import convert as cv\ndef run():\n    return cv()\n"
        )
        self.put("helper.py", "def convert():\n    return 1\n")
        self.put("unrelated.py", "def convert():\n    return 2\n")
        facts = self.facts()
        self.assertEqual(
            {f["file"] for f in facts["functions"]}, {"flow.py", "helper.py"}
        )
        self.assertEqual(facts["edges"][0]["basis"], "explicit_import")

    def test_python_self_annotated_parameter_and_shadowing(self):
        self.put(
            "flow.py",
            """class Worker:
    def send(self):
        return 1
    def run(self, other: Worker):
        self.send()
        other.send()
def shadow(other: Worker):
    other = object()
    other.send()
""",
        )
        facts = self.facts("Worker::run")
        self.assertEqual(len(facts["functions"]), 2)
        self.assertTrue(all(e["status"] == "syntax_candidate" for e in facts["edges"]))
        self.assertTrue(
            any(
                e["reason"] == "receiver_binding_may_be_shadowed"
                for e in self.facts("shadow")["edges"]
            )
        )

    def test_python_dynamic_callable_is_not_a_same_named_function(self):
        self.put(
            "flow.py",
            "def callback():\n    return 1\ndef run(callback):\n    return callback()\n",
        )
        facts = self.facts()
        self.assertEqual(len(facts["functions"]), 1)
        self.assertEqual(facts["edges"][0]["status"], "unresolved")

    def test_python_nested_functions_are_selectable_and_can_be_followed(self):
        self.put(
            "flow.py",
            "def run():\n    def child():\n        return 1\n    return child()\n",
        )
        self.assertEqual(
            {f["qualified"] for f in self.facts()["functions"]}, {"run", "run::child"}
        )

    def test_python_static_method_does_not_gain_an_implicit_receiver(self):
        self.put(
            "flow.py",
            "class Worker:\n    def send(self):\n        return 1\n    @staticmethod\n    def run(self):\n        return self.send()\n",
        )
        self.assertEqual(self.facts("Worker::run")["edges"][0]["status"], "unresolved")

    def test_python_import_changes_stale_but_line_moves_do_not(self):
        source = "from one import send\ndef run():\n    return send()\n"
        self.put("flow.py", source)
        facts = self.facts()
        notes = blank_explanations(facts)
        self.put("flow.py", "\n\n" + source)
        self.assertTrue(all(validate_explanations(notes, self.facts()).values()))
        self.put("flow.py", source.replace("from one", "from two"))
        self.assertFalse(any(validate_explanations(notes, self.facts()).values()))

    def test_dart_async_errors_switch_and_closure_boundary(self):
        self.put(
            "flow.dart",
            """Future<String> run(Client client, String text) async {
  if (text.isEmpty) { throw ArgumentError('empty'); }
  try { await client.send(text); } on FormatException catch (e) { rethrow; }
  finally { close(); }
  final callback = () { hidden(); return 'nested'; };
  switch (text) { case 'ok': return text; default: return 'fallback'; }
}
""",
        )
        facts = self.facts()
        fn = choose(facts["functions"], "run")
        self.assertTrue(fn["async"])
        self.assertNotIn("hidden", [c["name"] for c in fn["calls"]])
        self.assertEqual(len(fn["returns"]), 2)
        self.assertTrue(any("rethrow" in e["expression"] for e in fn["errors"]))
        self.assertTrue(
            any(
                b["kind"] == "switch_statement" and len(b["arms"]) == 2
                for b in fn["branches"]
            )
        )

    def test_dart_this_typed_parameter_and_arrow_return(self):
        self.put(
            "flow.dart",
            "class Worker { int send() => 1; int run(Worker other) { this.send(); return other.send(); } }",
        )
        facts = self.facts("Worker::run")
        self.assertEqual(len(facts["functions"]), 2)
        self.assertTrue(all(e["status"] == "syntax_candidate" for e in facts["edges"]))
        self.assertTrue(choose(facts["functions"], "Worker::send")["returns"])

    def test_dart_prefixed_import_follows_explicit_relative_file(self):
        self.put("flow.dart", "import 'helper.dart' as tool; int run() => tool.send();")
        self.put("helper.dart", "int send() => 1;")
        self.put("unrelated.dart", "int send() => 2;")
        self.assertEqual(
            {f["file"] for f in self.facts()["functions"]}, {"flow.dart", "helper.dart"}
        )

    def test_dart_dynamic_and_generic_receivers_remain_unresolved(self):
        self.put(
            "flow.dart",
            "class Worker { int send() => 1; } void run<T>(T worker, dynamic other) { worker.send(); other.send(); }",
        )
        facts = self.facts()
        self.assertEqual(len(facts["functions"]), 1)
        self.assertTrue(all(e["status"] == "unresolved" for e in facts["edges"]))

    def test_dart_constructors_and_getters_have_distinct_entries(self):
        self.put(
            "flow.dart",
            "class Worker { Worker(); Worker.named(int n); int get size => 1; set size(int n) {} } Worker run() => Worker.named(1);",
        )
        index = build_index(self.repo, adapter_for("dart"), self.cache)
        names = {f["qualified"] for f in index["files"]["flow.dart"]["functions"]}
        self.assertEqual(
            names,
            {
                "Worker::Worker",
                "Worker::Worker.named",
                "Worker::get:size",
                "Worker::set:size",
                "run",
            },
        )
        self.assertEqual(len(self.facts()["functions"]), 2)

    def test_mixed_business_keeps_languages_and_never_guesses_cross_language_calls(
        self,
    ):
        self.put("ui.dart", "int run() => helper();")
        self.put("service.py", "def helper():\n    return 1\n")
        self.put("lib.rs", "fn helper() {}")
        manifest = {
            "schema_version": 1,
            "nodes": [
                {"id": "ui", "sources": [{"file": "ui.dart", "symbol": "run"}]},
                {
                    "id": "service",
                    "sources": [{"file": "service.py", "symbol": "helper"}],
                },
                {"id": "core", "sources": [{"file": "lib.rs", "symbol": "helper"}]},
            ],
        }
        index = build_index(self.repo, adapter_for("auto"), self.cache)
        facts = extract_business(index, manifest, 2, 16)
        self.assertEqual(
            [
                choose(facts["functions"], i)["sources"][0]["kind"]
                for i in facts["root_ids"]
            ],
            ["dart_function", "python_function", "rust_function"],
        )
        self.assertEqual(facts["edges"][0]["status"], "unresolved")
        notes = blank_explanations(facts)
        self.put("service.py", "def helper():\n    return 2\n")
        current = extract_business(
            build_index(self.repo, adapter_for("auto"), self.cache), manifest, 2, 16
        )
        self.assertEqual(
            validate_explanations(notes, current),
            {"business::ui": True, "business::service": False, "business::core": True},
        )

    def test_mixed_and_single_language_caches_do_not_evict_each_other(self):
        self.put("lib.rs", "fn run() {}")
        self.put("flow.py", "def run():\n    pass\n")
        for language in ["auto", "rust", "python"]:
            build_index(self.repo, adapter_for(language), self.cache)
        self.assertEqual(
            build_index(self.repo, adapter_for("auto"), self.cache)["stats"][
                "reused_files"
            ],
            2,
        )

    def test_cli_both_new_languages_and_full_html_reuse(self):
        for language, suffix, text in [
            ("python", ".py", "def run():\n    return 1\n"),
            ("dart", ".dart", "int run() => 1;"),
        ]:
            self.put("flow" + suffix, text)
            args = [
                "function",
                "--repo",
                str(self.repo),
                "--file",
                "flow" + suffix,
                "--symbol",
                "run",
                "--out",
                str(self.root / language),
                "--cache",
                str(self.cache),
            ]
            with contextlib.redirect_stdout(io.StringIO()) as capture:
                self.assertEqual(main(args), 0)
                self.assertEqual(main(args), 0)
            summary = json.loads(capture.getvalue().splitlines()[-1])
            self.assertTrue(summary["html_reused"])
            self.assertTrue((self.root / language / "index.html").is_file())

    def test_invalid_new_language_files_are_rejected(self):
        for language, text in [
            ("python", "def run(:\n pass"),
            ("dart", "void run( { broken"),
        ]:
            self.assertTrue(adapter_for(language).parse(text, "invalid")["parse_error"])

    def test_parameter_hides_a_same_named_import_in_both_languages(self):
        samples = [
            (
                "flow.py",
                "import helper as client\ndef run(client):\n    return client.send()\n",
                "helper.py",
                "def send():\n    return 1\n",
            ),
            (
                "flow.dart",
                "import 'helper.dart' as client; int run(client) => client.send();",
                "helper.dart",
                "int send() => 1;",
            ),
        ]
        for file, source, helper, implementation in samples:
            self.put(file, source)
            self.put(helper, implementation)
            self.assertEqual(self.facts(file=file)["edges"][0]["status"], "unresolved")

    def test_python_nested_method_closure_does_not_invent_a_bare_method_call(self):
        self.put(
            "flow.py",
            "class Worker:\n    def send(self):\n        return 1\n    def run(self):\n        def child():\n            return send()\n        return child()\n",
        )
        facts = self.facts("Worker::run::child")
        self.assertEqual(facts["edges"][0]["status"], "unresolved")

    def test_python_rebound_module_import_does_not_follow_old_binding(self):
        self.put(
            "flow.py",
            "from helper import send\nsend = None\ndef run():\n    return send()\n",
        )
        self.put("helper.py", "def send():\n    return 1\n")
        self.assertEqual(self.facts()["edges"][0]["status"], "unresolved")

    def test_python_default_argument_global_changes_evidence(self):
        source = "LIMIT = 1\ndef run(value=LIMIT):\n    return value\n"
        self.put("flow.py", source)
        notes = blank_explanations(self.facts())
        self.put("flow.py", source.replace("LIMIT = 1", "LIMIT = 2"))
        self.assertFalse(any(validate_explanations(notes, self.facts()).values()))

    def test_class_method_body_changes_do_not_stale_unrelated_method(self):
        samples = [
            (
                "flow.py",
                "class Worker:\n    def run(self) -> Worker:\n        return self\n    def other(self):\n        return 1\n",
            ),
            ("flow.dart", "class Worker { Worker run() => this; int other() => 1; }"),
        ]
        for file, source in samples:
            self.put(file, source)
            facts = self.facts("Worker::run", file=file)
            notes = blank_explanations(facts)
            self.put(
                file, source.replace("return 1", "return 2").replace("=> 1", "=> 2")
            )
            self.assertTrue(
                all(
                    validate_explanations(
                        notes, self.facts("Worker::run", file=file)
                    ).values()
                )
            )

    def test_referenced_class_field_changes_stale_explanations(self):
        for file, source in [
            (
                "flow.py",
                "class Worker:\n    limit: int = 1\n    def run(self) -> Worker:\n        return self\n",
            ),
            (
                "flow.dart",
                "class Worker { final int limit = 1; Worker run() => this; }",
            ),
        ]:
            self.put(file, source)
            facts = self.facts("Worker::run", file=file)
            notes = blank_explanations(facts)
            self.put(file, source.replace("= 1", "= 2"))
            self.assertFalse(
                any(
                    validate_explanations(
                        notes, self.facts("Worker::run", file=file)
                    ).values()
                )
            )

    def test_dart_callable_field_is_not_assumed_to_be_a_top_level_function(self):
        self.put(
            "flow.dart",
            "int send() => 1; class Worker { final Function send; Worker(this.send); int run() => send(); }",
        )
        self.assertEqual(self.facts("Worker::run")["edges"][0]["status"], "unresolved")

    def test_dart_rebound_parameter_keeps_receiver_unresolved(self):
        self.put(
            "flow.dart",
            "class Worker { int send() => 1; } void run(Worker worker) { worker = Worker(); worker.send(); }",
        )
        edge = next(e for e in self.facts()["edges"] if e["name"] == "worker.send")
        self.assertEqual(edge["status"], "unresolved")

    def test_invalid_indexed_business_source_cannot_be_laundered_as_context(self):
        self.put("bad.py", "def run(:\n pass")
        index = build_index(self.repo, adapter_for("auto"), self.cache)
        manifest = {
            "nodes": [{"id": "bad", "sources": [{"file": "bad.py", "line": 1}]}]
        }
        with self.assertRaisesRegex(ValueError, "语法错误"):
            extract_business(index, manifest, 0, 16)

    def test_dart_import_visibility_and_default_constructor(self):
        self.put(
            "flow.dart",
            "import 'helper.dart' as api hide send; class Worker { Worker(); } Worker run() { api.send(); return Worker(); }",
        )
        self.put("helper.dart", "int send() => 1;")
        facts = self.facts()
        self.assertEqual(
            next(e for e in facts["edges"] if e["name"] == "api.send")["status"],
            "unresolved",
        )
        self.assertIn("Worker::Worker", {f["qualified"] for f in facts["functions"]})

    def test_python_imported_type_alias_is_bound_as_evidence(self):
        self.put(
            "flow.py",
            "from helper import Worker as Client\ndef run(value: Client) -> Client:\n    return value\n",
        )
        self.put("helper.py", "class Worker:\n    limit: int = 1\n")
        facts = self.facts()
        self.assertEqual([t["name"] for t in facts["types"]], ["Worker"])
        notes = blank_explanations(facts)
        self.put("helper.py", "class Worker:\n    limit: int = 2\n")
        self.assertFalse(any(validate_explanations(notes, self.facts()).values()))

    def test_python_conditional_import_is_explicitly_unresolved(self):
        self.put(
            "flow.py",
            "if flag:\n    from one import send\nelse:\n    from two import send\ndef run():\n    return send()\n",
        )
        self.put("two.py", "def send():\n    return 2\n")
        facts = self.facts()
        self.assertEqual(
            facts["edges"][0]["reason"], "conditional_or_multiple_import_bindings"
        )
        notes = blank_explanations(facts)
        self.put(
            "flow.py",
            (self.repo / "flow.py").read_text().replace("if flag", "if other_flag"),
        )
        self.assertFalse(any(validate_explanations(notes, self.facts()).values()))


if __name__ == "__main__":
    unittest.main()
