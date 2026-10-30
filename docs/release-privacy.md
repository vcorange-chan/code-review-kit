# Publication privacy

Run `python scripts/check_release.py source` before committing. The release policy is
an explicit list of public files and normalized UTF-8/LF content hashes. Binary images
are pinned to reviewed bytes. The policy itself is content-scanned, not self-hashed.
Do not blindly regenerate the list or approve a changed hash without reviewing its diff.

Private review data stays under ignored local directories. Public examples must be
fictional and reviewed before approval. Never put a real private project name into a
public denylist or a regression fixture: use fictional strings in tests. Put actual
terms in ignored `.local/privacy-denylist.json` or the local `REVIEW_KIT_PRIVATE_TERMS`
JSON array environment variable. Real terms are not sent to GitHub. CI uses an explicit
empty array for its generic baseline; local push and publish checks add private terms.
The checker never prints matched content. An explicit local `--report` stores details;
that diagnostic is itself prohibited publication data.

`git config --local core.hooksPath .githooks` installs the optional repository-local
pre-push gate. It scans the proposed commit snapshots, their messages and ref names,
including intervening commits, instead of trusting only the working tree. It requires
the publisher's private-term configuration. Old branches without a release policy
are blocked until separately reviewed. Do not bypass this gate for routine publishing.

Skill ZIP creation copies only approved files. The Python build backend checks both
source and final wheel/sdist. Unknown files, symlinks, duplicate archive entries,
generated Review data and host absolute paths are rejected. Builds that fail their
final archive check do not return a publishable archive.

Use `scripts/prepare_release.py` to prepare an empty output directory and `--verify`
to recheck the actual assets. It builds the Skill and wheel and derives both language
demos from the pinned synthetic fixture, with a fixed synthetic timestamp for exact
comparison. Raw user output is never promoted to a demo. The directory must contain
only the four declared assets and their checksums.

The explicit `--publish TAG --target SHA --notes FILE` option rechecks the directory,
requires the matching clean commit and version, scans release notes and uploads only
those declared files. CI performs the same preparation and verification before artifact
upload. No upload occurs during an ordinary local Review.

These checks guard against accidental inclusion; they do not prove that arbitrary
prose, images or deliberately approved source are free of private meaning. Human
review of the approved hashes remains required. Git history is a separate matter:
editing current files does not remove old commits. Rewriting published refs changes
commit identities and can disrupt clones and pinned versions; cached or downloaded
copies may remain even after rewriting.
