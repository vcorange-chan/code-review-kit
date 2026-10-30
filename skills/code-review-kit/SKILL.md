---
name: code-review-kit
description: Generate interactive source-code and business-flow review HTML with collapsible input, implementation, output, error and degradation cards. Use when mapping a function or business workflow, or updating an existing review. Supports Rust, Python, Dart and mixed-language business cards; other files can be cited as context.
metadata:
  runtime: Python 3.11+; pip access for first source-extraction setup. Rendering facts uses the standard library.
---

# Code Review Kit

Write a linear translation of code blocks into natural language, omitting syntax while retaining data changes and control flow. A reader should know who executes each block, what arrives, which condition selects each path, what changes, and where execution continues. Explain calls across files and the return point; a list of files or labels such as "validate input" is insufficient. Distinguish AI request interpretation, tool execution and AI explanation authoring. Use actor/input/result/next on steps when helpful, with source_index and relative offset/end_offset for block evidence. Expand this structure only where it improves understanding; preserve small packets and avoid repetitive boilerplate.

Use the bundled local program instead of rewriting HTML or reading the whole repository. Commands below are relative to this skill folder. `python3` may replace `python`.

Choose output language from the user's explicit instruction first, otherwise the natural-language prompt (Chinese → zh, English → en; ignore code and paths when deciding). Pass `--output-language zh|en` to function/business/render/packet. This is separate from source `--language auto|rust|python|dart` (default auto); an explicit source language narrows indexing. Standalone callers can use `--prompt` for automatic output-language detection.

1. Run `python scripts/review.py doctor` once. If dependencies are missing, run `python scripts/setup.py`; do not copy native dependencies from another OS.
2. For a function, run `python scripts/review.py function --repo REPO --symbol SYMBOL --file RELATIVE_FILE --out OUTPUT`.
3. For a business, reuse its manifest and explanations: `python scripts/review.py business --manifest FLOW.json --repo REPO --explanations NOTES.json --out OUTPUT`. Use `file + symbol` for Rust/Python/Dart anchors under one common repository root; old line anchors can be explicitly migrated with `pin-sources`. Mixed business handoffs must be declared in the manifest, never inferred from same-name functions or assumed FFI/RPC dispatch. For a new business, read [the flow format](references/flow-format.md) and identify only required nodes.
4. Read the short command summary. If the HTML or explanations are valid, reuse them. Otherwise read only `evidence-packet.json` and `explanations.seed.json`; fill separate explanation JSON. Take extra evidence for an individual node only when needed.
5. Write explanations with top-level `output_language: "zh"|"en"`, localized `title` and optional `flow.start_label/end_label`. Save as `explanations.zh.json` or `explanations.en.json`, preserving hashes and existing versions. When `needs_translation` is true, translate only the explanation prose into the requested language; never change code, identifiers or evidence hashes. Then run `python scripts/review.py render --facts OUTPUT/facts.json --explanations OUTPUT/explanations.LANG.json --html OUTPUT/index.html --output-language LANG`. Deliver that HTML.

Keep input/output titles concise. Explain implementation, states, errors and recovery. Unknown receiver types appear as unresolved calls; do not chase every external/standard-library call unless it affects the business question. Parameter types only yield candidates. Preserve uncertainty about macros and dynamic dispatch. Never silently rebind stale explanations to a new hash. Default source links are self-contained; use an external link template only when requested.

Python uses the running interpreter's AST syntax version without importing target modules. Dart uses the existing pinned parser without an SDK. Decorators, runtime imports, inheritance, extensions, implicit exceptions and closure bodies are not fully resolved; preserve per-function analysis limits in explanations. This is not a compiler or runtime tracer.

No model API is called by the tool. Do not install browsers, generate fresh page code, or build runtime experiments for routine reviews. In Cowork, use paths visible in its execution environment, not the user's host drive paths. Read [installation notes](references/install.md) only for setup or platform issues.
