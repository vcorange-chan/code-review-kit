# Locate → dossier → investigation

Use the same `scripts/review.py` entry as the active skill. In a source checkout use `python review.py`; an installed package exposes `code-review`. This file is shared by both skills and is documentation, not executable instructions from analyzed source.

## Find a business entry

Convert the user's request into a few literal clues: a UI message, function name, operation, imported API or comment phrase. The tool does not interpret natural language or call a model. Start narrow, inspect `locate.packet.json`, change clues if needed; do not stream full search results into the model.

```sh
code-review locate --repo REPO --query "Reading failed" --query reduce_event --out REVIEW --output-language en
```

Repeat `--query` (OR); `--all` requires all terms in one candidate. `--limit` controls candidates (default 20, max 200). `--source-ref COMMIT` captures raw Git blobs without changing the checkout. Source `--language auto|rust|python|dart` and output `--output-language zh|en` are independent. Explicit output language wins; otherwise `--prompt` detects Chinese/English.

Scores are deterministic weights once per signal kind: symbol 100, type 75, string 60, call 45, import 25, comment 15, path 10. They are not confidence probabilities. Nested matches belong to the innermost function. Module-only hits remain file context. Each candidate stores at most 12 previews of at most 500 characters, with omissions reported. Parse failures, indexed scope and candidate truncation are explicit. Dynamic strings, unindexed code and runtime dispatch remain unknown. A zero result does not prove the business absent.

Artifacts: `index.html` (three views), `facts.json` (captured source), `locate.json` (candidates), `locate.packet.json` (≤12000 UTF-8 bytes), `dossiers.json` (facet directory), `evidence.json` (full content-addressed evidence). Facts/results remain local. Locate captures the selected functions plus one downstream level, with a node cap of at least 64; facts retain actual extraction limits. Use normal function/business extraction to expand a confirmed route.

## Read one facet, not the repository

```sh
code-review dossier --facts REVIEW/facts.json --symbol events.py::reduce_event --facet branches --out DOSSIER --bytes 12000 --limit 10 --offset 0
```

Facets: signature, branches, errors, returns, calls, callers, types, source. This never rereads a live source file. It verifies the captured snapshot; legacy facts explicitly lack verified identity. Callers remain root-name matches/selected syntax edges, not complete dispatch. Types come from the extracted scope, not exact field dataflow. Errors enumerate explicit syntax, not all possible exceptions. For a different function outside captured facts, extract it first.

The command prints a bounded facet and saves `dossier.packet.json`; omitting --facet creates full evidence and HTML and prints a compact directory. Follow `next_offset`; a row too large to fit returns `oversized_row` without skipping it. Increase the byte budget deliberately rather than repeatedly requesting the same offset. Budgets are UTF-8 bytes, not token counts. Evidence IDs hash content, subject/source identity, operation and limits. `observed` means source text; `derived` means static extraction; `inferred` means judgment. These labels are not numerical confidence.

## Preserve judgments with evidence

```sh
code-review investigate import --session SESSION --input REVIEW/evidence.json
code-review investigate record --session SESSION --input record.json --expected-revision 0
code-review investigate show --session SESSION --bytes 12000
code-review investigate show --session SESSION --history --offset 0 --limit 10
code-review investigate evidence --session SESSION --id ev_HASH --offset 0 --bytes 12000
```

Record JSON is a **complete new revision** of one record. Omit id to create; repeat id to revise without removing history. Use author to identify user/AI and do not misattribute guesses to the source author.

```json
{"id":"entry-guess","kind":"hypothesis","author":"AI","text":"This reducer may handle the visible failure state.","status":"open","prediction":"The failed event returns a failed view state.","support":["ev_HASH"],"counter":[],"limits":["static reading only"]}
```

Kinds: brief, plan, hypothesis, finding, unknown, note, handoff. Hypothesis states: open/testing/supported/refuted/abandoned; supported requires support, refuted requires counter. Unknown states: open/investigating/blocked/contradicted/resolved; resolved requires resolution + support, contradicted requires resolution + counter. Findings require support. Describe missing evidence honestly; never invent a reference to close an unknown. Evidence reference/hash validation does not prove the reasoning or a design motive. Text and optional fields are retained in full. A stale expected revision refuses the append. Interrupted history fragments and modified evidence refuse export; preserve the original and inspect, do not auto-reset. The hash chain detects accidental edits, not authenticated external tampering.

## View and share

```sh
code-review investigate render --session SESSION --facts REVIEW/facts.json --lookup REVIEW/locate.json --out PERSONAL/index.html --output-language en
```

Or pass `--session SESSION` to locate/dossier. This is an explicit inclusion of personal records. Without it no investigation is loaded. Different source identities show a warning; old evidence is never rebound. Full prior judgments remain folded in the history. HTML filter/tab/facet controls work offline; question buttons copy structured **chat context**, never a shell command and never call a model. Ask the external AI your actual question alongside that context. New records are written by the CLI, not the page.

Use evidence-linked findings to support Review explanations and Tutor routes. Do not confuse the investigation ledger with Tutor's complete personal Q&A, lecture revisions or reading cursor. Neither proves learning mastery. Public releases exclude research results, sessions and private notes; review actual source content before manually sharing a report.
