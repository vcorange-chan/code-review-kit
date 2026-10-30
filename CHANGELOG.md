# Changes

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
