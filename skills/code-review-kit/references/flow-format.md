# Business views and branches

One business node can cite multiple functions and non-Rust context. Stable node IDs belong to the business; they are independent of function names. Analysis still only parses Rust.

```json
{
  "schema_version": 1,
  "repository": ".",
  "title": "Import workflow",
  "start_label": "Submit",
  "end_label": "Ready",
  "nodes": [
    {"id":"read","label":"read_source","sources":[{"file":"src/lib.rs","line":1,"end_line":3,"label":"Read source"}]},
    {"id":"save","label":"save_result","sources":[{"file":"src/lib.rs","line":4,"label":"Save result"}]}
  ],
  "edges": [
    {"from":"read","to":"save","kind":"success"},
    {"from":"read","to":"read","kind":"resume","branch":"optional","port":"output","label":"Keep raw input and continue"}
  ]
}
```

The success edges connect the ordered nodes in one vertical spine. Resume edges identify a specific degradation branch and target node, at `input` or `output`; forward, same-node and backward targets are allowed. A terminal error branch has no resume edge. Node IDs use letters, numbers, underscores and hyphens.

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
