# Investigation during tutoring

Use the shared offline core, not a second searcher or notebook format. The full protocol is bundled at `scripts/tool/reviewkit/research-workflow.md`; in a source checkout it is `reviewkit/research-workflow.md` at the repository root.

When the business entry is unknown, run `python scripts/review.py locate --repo REPO --query LITERAL --source-ref COMMIT --out OUTPUT`. Read only locate.packet.json. Inspect needed facets with `dossier --facts OUTPUT/facts.json --symbol ID --facet branches --out DOSSIER --bytes 12000`; candidate calls are not runtime proof. Reuse already captured evidence rather than rereading the repository.

For work spanning sessions, import OUTPUT/evidence.json with `investigate import --session SESSION --input ...`. Append a complete record using `investigate record --session SESSION --input record.json --expected-revision N`. Record brief/plan/hypothesis/finding/unknown/note/handoff; refer to evidence IDs in support/counter. Unknown resolution needs text and evidence. Use `investigate show --session SESSION` to recover, or --history for original revisions. This ledger does not replace complete Tutor discussion, lecture revisions or cursor files and does not establish mastery.

Personal HTML is opt-in with `investigate render --session SESSION ...` or locate/dossier --session. Do not include it in a public lecture by default. Keep old judgments and their original source identity; do not rebind evidence or substitute summaries for originals.
