"""Portable entry point; no network, model API, or subprocess shell evaluation."""
from pathlib import Path
import sys
if sys.version_info < (3,11):
    raise SystemExit('Code Review Kit requires Python 3.11+ for portable parser installation.')
from reviewkit.runtime import dependency_paths
sys.path[:0]=[str(p) for p in dependency_paths(Path(__file__).resolve().parent)]
from reviewkit.cli import main

if __name__ == '__main__':
    raise SystemExit(main())
