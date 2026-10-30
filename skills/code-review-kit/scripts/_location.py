from pathlib import Path


def tool_root():
    here = Path(__file__).resolve()
    bundled = here.parent / "tool"
    root = bundled if (bundled / "review.py").is_file() else here.parents[3]
    if not (root / "reviewkit/cli.py").is_file():
        raise SystemExit("Missing bundled tool. Install the complete skill ZIP or Git package.")
    return root
