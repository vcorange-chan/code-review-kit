# Install and move between environments

Pi: install the Git repository as a Pi package (`pi install git:github.com/OWNER/code-review-kit@v0.2.0`). It discovers `skills/code-review-kit`; no TypeScript extension or model API is needed. Use `/skill:code-review-kit` to invoke explicitly.

Cowork: upload the release's `code-review-kit-skill.zip` in Customize → Skills → Upload a skill, with code execution enabled. The ZIP contains the complete skill and Python tool. Supply repository files in a folder accessible to Cowork's execution environment. Run setup there once if extracting source. Host paths such as a Windows drive letter are not portable; override the business manifest with `--repo` pointing to the visible folder. Source links in a report remain local to the environment where it was built.

The ZIP omits native binaries and caches. `python scripts/setup.py` installs `ast-grep-py` for the actual Python and OS. It needs package-network access. If network access is disabled, prepare compatible dependencies beforehand; do not repeatedly retry or pretend installation succeeded. Rendering existing facts is standard-library only and does not require the parser.

Standalone tool: `python -m pip install .` from a source checkout installs `code-review`. Alternatively use `python review.py` and the isolated `.deps` installer. `rg` speeds file listing but is optional.

The program runs locally without model API calls; this does not make Pi/Cowork model usage offline. Explain only changed nodes and keep tool output small. Never upload proprietary repository snapshots when sharing the skill itself.
