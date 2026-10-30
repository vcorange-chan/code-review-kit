"""CLI used by developers, AI, Git hooks and CI; no matched private text on stdout."""

from pathlib import Path
import argparse, json, sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reviewkit.runtime import dependency_paths

sys.path[:0] = [str(p) for p in dependency_paths(ROOT)]
from reviewkit.release_privacy import check_source, check_asset, check_push, PrivacyError


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["source", "assets", "git-push"])
    parser.add_argument("assets", nargs="*")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--require-private-terms", action="store_true")
    parser.add_argument(
        "--report", help="Local diagnostic JSON; keep it outside publication inputs"
    )
    args = parser.parse_args()
    root = Path(args.root)
    try:
        if args.mode == "git-push":
            result = check_push(root, sys.stdin.read().splitlines())
        else:
            result = check_source(root, args.require_private_terms)
            if args.mode == "assets":
                if not args.assets:
                    raise PrivacyError("assets-required", "assets")
                result["assets"] = [
                    check_asset(root, Path(p), args.require_private_terms) for p in args.assets
                ]
        print(json.dumps(result))
        return 0
    except Exception as error:
        if args.report:
            report = Path(args.report)
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text(
                json.dumps(
                    {
                        "privacy_check_report": True,
                        "rule": getattr(error, "rule", type(error).__name__),
                        "entry": str(getattr(error, "entry", "")),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": (
                        str(error)
                        if isinstance(error, PrivacyError)
                        else "Privacy check could not complete: " + type(error).__name__
                    ),
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
