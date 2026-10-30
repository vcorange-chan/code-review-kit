---
name: code-review-kit
description: Generate interactive source-code and business-flow review HTML with collapsible input, implementation, output, error and degradation cards. Use when mapping a function or business workflow, or updating an existing review. Rust extraction; other source files can be cited as context.
metadata:
  runtime: Python 3.11+; pip access for first source-extraction setup. Rendering facts uses the standard library.
---

# Code Review Kit

Use the bundled local program instead of rewriting HTML or reading the whole repository. Commands below are relative to this skill folder. `python3` may replace `python`.

Choose output language from the user's explicit instruction first, otherwise the natural-language prompt (Chinese → zh, English → en; ignore code and paths when deciding). Pass `--output-language zh|en` to function/business/render/packet. This is separate from `--language rust`. Standalone callers can use `--prompt` for automatic detection.

1. Run `python scripts/review.py doctor` once. If dependencies are missing, run `python scripts/setup.py`; do not copy native dependencies from another OS.
2. For a function, run `python scripts/review.py function --repo REPO --symbol SYMBOL --file RELATIVE_FILE --out OUTPUT`.
3. For a business, reuse its manifest and explanations: `python scripts/review.py business --manifest FLOW.json --repo REPO --explanations NOTES.json --out OUTPUT`. Use `file + symbol` for Rust anchors; old line anchors can be explicitly migrated with `pin-sources`. For a new business, read [the flow format](references/flow-format.md) and identify only required nodes.
4. Read the short command summary. If the HTML or explanations are valid, reuse them. Otherwise read only `evidence-packet.json` and `explanations.seed.json`; fill separate explanation JSON. Take extra evidence for an individual node only when needed.
5. Write explanations with top-level `output_language: "zh"|"en"`, localized `title` and optional `flow.start_label/end_label`. Save as `explanations.zh.json` or `explanations.en.json`, preserving hashes and existing versions. When `needs_translation` is true, translate only the explanation prose into the requested language; never change code, identifiers or evidence hashes. Then run `python scripts/review.py render --facts OUTPUT/facts.json --explanations OUTPUT/explanations.LANG.json --html OUTPUT/index.html --output-language LANG`. Deliver that HTML.

Keep input/output titles concise. Explain implementation, states, errors and recovery. Unknown receiver types appear as unresolved calls; do not chase every external/standard-library call unless it affects the business question. Parameter types only yield candidates. Preserve uncertainty about macros and dynamic dispatch. Never silently rebind stale explanations to a new hash. Default source links are self-contained; use an external link template only when requested.

No model API is called by the tool. Do not install browsers, generate fresh page code, or build runtime experiments for routine reviews. In Cowork, use paths visible in its execution environment, not the user's host drive paths. Read [installation notes](references/install.md) only for setup or platform issues.
