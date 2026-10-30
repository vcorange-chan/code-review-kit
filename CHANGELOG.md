# Changes

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
