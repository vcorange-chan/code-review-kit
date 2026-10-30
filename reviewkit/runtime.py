"""Writable state is separate from a potentially read-only installed skill."""
from pathlib import Path
import os
import platform
import sys
import tempfile
from . import __version__


def state_root():
    base=Path(os.environ.get('CODE_REVIEW_KIT_STATE',str(Path(tempfile.gettempdir())/'code-review-kit')))
    return base/__version__/(sys.implementation.cache_tag+'-'+platform.system()+'-'+platform.machine())


def dependency_paths(home):
    return [state_root()/'deps',home/'.deps']


def index_cache(home):
    legacy=home/'.cache'
    return legacy if legacy.is_dir() and os.access(legacy,os.W_OK) else state_root()/'index'
