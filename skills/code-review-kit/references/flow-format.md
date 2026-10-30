# Business views and branches

## Linear code-block explanations

Explain each block in execution order, including the actual condition and both outcomes, data changes and the next destination. For multiple files, name each actor, the call, its arguments and the return point. Keep syntax and source excerpts behind source links, not in the primary narrative. Claims about execution require runtime evidence; static reading must remain labelled as such.

Steps retain `title/detail/reference`. Optional `actor/input/result/next` make the handoff explicit. When these fields are used, opening the implementation reveals the sequential step bodies. `source_index` selects one of the referenced business node's `sources`; without it the reference identifies a selected function. `offset/end_offset` select inclusive lines relative to that evidence's start, and must stay within it. Defaults link the whole selected range. Never invent a source path or attach a description to an unrelated block.

```json
{"title":"Resolve the repository","actor":"cli.main","input":"A relative repository path from the manifest","detail":"When the path is relative, resolve it from the manifest directory; otherwise keep the absolute path. Then check that the directory exists.","result":"An existing absolute repository directory, or an error","next":"Build the source index","reference":"business::read","source_index":0,"offset":2,"end_offset":6}
```

The numeric example assumes that those lines are part of the selected source; derive real offsets from evidence. The program checks structure and source bounds, not whether an explanation is semantically complete. Legacy title/detail-only steps remain supported.

Output language is separate from source analysis. Pass `--output-language zh|en` according to the user's explicit instruction or prompt language. Explanation JSON declares `output_language` (legacy = zh); top-level `title` and `flow.start_label/end_label` provide localized labels. Keep each language in its own explanation file, preserving evidence hashes and the other language. Code and identifiers are never translated. A missing language is requested rather than silently mixing prose.

One business node can cite multiple functions and non-Rust context. Stable node IDs belong to the business; they are independent of function names. Analysis still only parses Rust.

```json
{
  "schema_version": 1,
  "repository": ".",
  "title": "Import workflow",
  "start_label": "Submit",
  "end_label": "Ready",
  "nodes": [
    {"id":"read","label":"read_source","sources":[{"file":"src/lib.rs","symbol":"read_source","label":"Read source"}]},
    {"id":"save","label":"save_result","sources":[{"file":"src/lib.rs","symbol":"save_result","label":"Save result"}]}
  ],
  "edges": [
    {"from":"read","to":"save","kind":"success"},
    {"from":"read","to":"read","kind":"resume","branch":"optional","port":"output","label":"Keep raw input and continue"}
  ]
}
```

The success edges connect the ordered nodes in one vertical spine. Resume edges identify a specific degradation branch and target node, at `input` or `output`; forward, same-node and backward targets are allowed. A terminal error branch has no resume edge. Node IDs use letters, numbers, underscores and hyphens.

Rust anchors should use `file + symbol` (short qualified name or full ID), for functions or named types. The index supplies current lines. Optional `offset/end_offset` select a range relative to the symbol start; edits within that function/range still require review. Non-Rust context uses explicit `line/end_line`. Legacy Rust line anchors remain readable with a warning. `pin-sources` writes a new manifest without rebinding explanations.

Explain a view under `cards["business::read"]` in explanations JSON. Preserve its evidence hash from the generated seed. Optional `inputs` and `outputs` are detail arrays; `scope` and `state` describe the business. `steps` contain title, detail and optional reference symbol ID.

```json
{
  "id":"optional", "kind":"degrade", "side":"right",
  "title":"Optional cleanup unavailable", "state":"Raw input retained",
  "items":[{"condition":"Cleanup fails","returns":"Raw input","handling":"Continue to the normal output"}]
}
```

Place this object in the card's `branches` array. Use `kind: "error"` for a stopping/error branch, `kind: "degrade"` for a recoverable branch. Both kinds use the same condition/return/handling item shape. All business descriptions are plain text, never HTML.

Run `business` without explanations first to generate facts and seed. A report with missing explanations labels them as automatic; it does not invent semantics. After writing notes, run `render`. Keep success order, resume targets and source references in the manifest so they need not be rediscovered each time.
