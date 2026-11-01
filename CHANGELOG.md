# Changes

## 0.8.0

- Verify portable source identities and read fixed Git blobs without modifying the learning workspace; distinguish workspace snapshots from commit evidence.
- Bind selection actions and discussions to their actual revision, retain full quotations and unmatched answers, and archive complete previous views through atomic tutor operations.
- Add step drafts, automatic fold complements, fact-derived signatures, bounded reusable step packets, matching Review behavior reuse, and resumable reading cursors with stale/duplicate request checks.
- Separate reading progress, fixed behavior and counterfactual reasoning in lecture schema 2; retain legacy schema 1 with explicit notices and add a fictional event-driven Python lesson.

- Add the copy-tutor skill and core `lecture` / `discuss` commands. Lectures cut code lines from facts snapshots, verify that every line of a node is shown or folded with a destination, and bind each step to its node digest so that source changes are marked for review.
- Record each reason's kind (recorded, inferred, teaching) together with its support and limits. Decisions are optional. Out-of-scope folds collapse on the page while full coverage is still enforced.
- Append questions and notes to a separate JSONL file bound to the lecture, step and revision. Show them per step; keep records for missing steps visible; render public lectures without them.
- Build `copy-tutor-skill.zip` alongside the Review skill. Each ZIP bundles the shared tool, is checked against the release policy, and is executed by the smoke test.
- Add a fictional bilingual-label lecture example for the document pipeline.

## 0.7.1

- Keep compact type summaries separate from verbatim source snapshots for all languages; reject conflicting original lines and preserve missing-source notices for legacy facts.
- Exclude full type source from bounded AI packets, preserving compact evidence and existing staleness rules.
- Share one repository-local ignore policy between rg and Python enumeration, including nested ignore files and consistent generated/private directory exclusions; use pinned pure-Python pathspec.
- Add regressions for source-line fidelity, legacy snapshots, independent evidence, ignore negation/precedence and both enumeration providers.

## 0.7.0

- Add Python AST and Dart ast-grep adapters with function/method entries, branches, explicit error/return facts and conservative call hints; no new runtime dependency or target-code execution.
- Default source language to auto, supporting explicit mixed Rust/Python/Dart business sources while keeping call candidates within the caller's language.
- Isolate single/mixed language caches, preserve language and limits in bounded evidence packets, and retain independent card staleness.
- Add bilingual fictional mixed-language examples and exercise all three languages from the packaged Pi/Cowork core.

## 0.6.0

- Keep public examples fictional and replace project-specific ignore entries with generic private-example exclusion.
- Add one offline source/archive/privacy checker with approved hashes, private-term configuration, safe diagnostics and evidence-derived public demos.
- Gate Skill ZIPs, Python wheel/sdist builds, Git pushes and CI publication artifacts; recheck actual files immediately before release upload.
- Preserve private reviews locally; no automatic upload or model API is added.

## 0.5.0

- Explain code blocks in execution order with actors, input, conditions, results and next destinations; clarify cross-file calls and return points in the shared AI/Skill contract.
- Add optional structured step fields and evidence-bound block links using relative offsets and source selection. Reject references outside selected evidence.
- Reveal sequential step bodies when implementation is expanded; retain legacy steps and existing card layout. Rename the vague limitations fold to Notes and limitations.
- Add Chinese/English fixtures showing validation, return and caller-side error handling as separate blocks.

## 0.4.0

- Add a full English README alongside the Chinese version.
- Select Chinese/English output from explicit choice or prompt language, shared by CLI, Pi and Cowork.
- Translate fixed UI, statuses, source-view controls and evidence guidance through one catalog; preserve source code and evidence identity.
- Keep explanation languages separate, request missing translations, and preserve the original prose and hashes.
- Add a complete English workflow fixture and bilingual browser/Skill verification.

## 0.3.0

- Keep every call visible as a candidate, ambiguous call or unresolved entry with a reason; conservatively infer direct parameter receiver types.
- Add stable symbol anchors and explicit migration of line-based business sources.
- Scope evidence attributes to relevant functions, modules and types instead of every item in a file.
- Embed navigable source snapshots by default; add relative, local and configurable remote/editor links.
- Split card rendering, link generation and page assembly into separate modules.
- Use platform-neutral instructions and add a screenshot of the public demo.
- Keep Rust as the only implemented analyzer; share the adapter contract with future languages.

Evidence rules changed: old explanations can require review. They are not automatically rebound.

## 0.2.0

Initial Rust extractor, business views, degradation returns, portable skill packaging and caching.
