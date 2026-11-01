# Investigation entry

The core and full protocol are bundled at `scripts/tool/reviewkit/research-workflow.md` inside an installed skill. In a source checkout, read `reviewkit/research-workflow.md` at the repository root. Read only the relevant section.

- Locate: `python scripts/review.py locate --repo REPO --query LITERAL --out OUTPUT`. Read `locate.packet.json`, not all facts.
- Dossier: `python scripts/review.py dossier --facts OUTPUT/facts.json --symbol ID --facet calls --out DOSSIER --bytes 12000`. Follow next_offset; preserve unresolved reasons and coverage.
- Persist evidence: `investigate import --session SESSION --input OUTPUT/evidence.json`.
- Record: `investigate record --session SESSION --input record.json --expected-revision N`. The record is a complete new revision; original history remains. Use brief/plan/hypothesis/finding/unknown/note/handoff. Finding requires supporting IDs. Resolving unknowns requires resolution text and evidence.
- Recover: `investigate show --session SESSION --bytes 12000`; `--history` pages original revisions. `investigate evidence --session SESSION --id ev_HASH` pages evidence.
- Personal HTML: `investigate render --session SESSION --facts OUTPUT/facts.json --lookup OUTPUT/locate.json --out PERSONAL/index.html`. Without explicit session inclusion, no private investigation is loaded.

Evidence IDs establish content and source identity, not reasoning truth. Investigation state is not learner mastery. Do not replace complete records with model summaries. Public bundles exclude investigation artifacts.
