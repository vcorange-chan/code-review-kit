---
name: code-review-kit
description: Generate interactive source-code and business-flow review HTML with collapsible input, implementation, output, error and degradation cards. Use when mapping a function or business workflow, or updating an existing review. Rust extraction; other source files can be cited as context.
metadata:
  runtime: Python 3.10+; pip access for first source-extraction setup. Rendering facts uses the standard library.
---

# Code Review Kit

Use the bundled local program instead of rewriting HTML or reading the whole repository. Commands below are relative to this skill folder. `python3` may replace `python`.

1. Run `python scripts/review.py doctor` once. If dependencies are missing, run `python scripts/setup.py`; do not copy native dependencies from another OS.
2. For a function, run `python scripts/review.py function --repo REPO --symbol SYMBOL --file RELATIVE_FILE --out OUTPUT`.
3. For a business, reuse its manifest and explanations: `python scripts/review.py business --manifest FLOW.json --repo REPO --explanations NOTES.json --out OUTPUT`. For a new business, read [the flow format](references/flow-format.md) and identify only the required nodes. The tool does not infer business order from references.
4. Read the short command summary. If the HTML or explanations are valid, reuse them. Otherwise read only `evidence-packet.json` and `explanations.seed.json`; fill separate explanation JSON. Take extra evidence for an individual node only when needed.
5. Run `python scripts/review.py render --facts OUTPUT/facts.json --explanations OUTPUT/explanations.json --html OUTPUT/index.html`. Deliver that HTML.

Keep input/output titles concise. Explain implementation, states, error conditions, returned values and recovery. References use source anchors or symbol IDs. Preserve uncertainty about macros, dynamic dispatch and dependencies outside the selected scope. A matching evidence hash does not establish runtime correctness. Never silently rebind stale explanations to a new hash.

No model API is called by the tool. Do not install browsers, generate fresh page code, or build runtime experiments for routine reviews. In Cowork, use paths visible in its execution environment, not the user's host drive paths. Read [installation notes](references/install.md) only for setup or platform issues.
