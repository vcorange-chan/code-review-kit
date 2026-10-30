"""Portable entry point; no network, model API, or subprocess shell evaluation."""
from pathlib import Path
import sys
if sys.version_info < (3,11):
    raise SystemExit('Code Review Kit requires Python 3.11+ for portable parser installation.')
sys.path.insert(0, str(Path(__file__).resolve().parent / '.deps'))
from reviewkit.cli import main

if __name__ == '__main__':
    raise SystemExit(main())
