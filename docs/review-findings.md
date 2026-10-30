# External review follow-up · 0.3

The seven observations were reproduced by source inspection and targeted tests.
Evidence matching is still source evidence, not runtime verification.

| Observation | Change | Verification |
| --- | --- | --- |
| Method calls silently stop traversal | Keep every parsed call, including unresolved receivers with a reason; use direct annotated parameter types conservatively. Generic method syntax is supported. Ambiguous dispatch is not expanded. | Receiver, shadowing, generic/dynamic dispatch, qualified external names and ambiguity regressions |
| Business anchors depend on line numbers | Prefer stable symbol IDs; resolve current lines on every index. Explicit `pin-sources` migration preserves selected ranges and leaves old explanations untouched. | Insert lines above a symbol; migrate a mixed Rust/context manifest |
| Unrelated attributes invalidate explanations | Hash attached function/owner attributes, visible imports and used local macros. Relevant type attributes remain evidence. | Unrelated derive stays current; own attributes, relevant derive and import cfg become stale |
| Source links leak host paths and fail when shared | Default embedded source snapshots with real HTML line targets. Explicit relative/local/template modes support other workflows. | No generator path in default HTML; every snapshot link has a target; URL escaping and scheme validation |
| Private-project and Windows-specific docs | Rewrite the workflow, decisions and install instructions around the common CLI and public synthetic fixture. | Public-file audit and isolated ZIP execution |
| Dense page-building code | Separate lexical analysis, language registry, card rendering, source links, HTML primitives and page assembly. Format Python conventionally. | Existing behavior regressions, JavaScript syntax and actual browser interaction checks |
| No visual preview | README includes the actual public demo screenshot. The optional CI preview job reproduces it from the fixed template and public data. | Preview job checks 14 current cards, 43 straight success segments and 5 resume paths before capture |

The preview job's browser dependency is development-only. Extraction and rendering remain
offline and do not need a browser or a model API. The example is synthetic; private project
manifests, source snapshots and caches are excluded from releases.

Only Rust analysis is implemented. Future Dart, Zig, C and Go adapters use the shared
contract in `reviewkit/languages.py`; they are not advertised as supported today.
