"""PEP 517 build gate; source and final archives use the same offline checker."""

from pathlib import Path
from setuptools import build_meta as original
from reviewkit.release_privacy import check_source, check_asset, check_sdist

ROOT = Path(__file__).resolve().parent

def get_requires_for_build_wheel(config_settings=None):
    check_source(ROOT)
    return original.get_requires_for_build_wheel(config_settings)

def get_requires_for_build_sdist(config_settings=None):
    check_source(ROOT)
    return original.get_requires_for_build_sdist(config_settings)

def prepare_metadata_for_build_wheel(metadata_directory, config_settings=None):
    check_source(ROOT)
    return original.prepare_metadata_for_build_wheel(metadata_directory, config_settings)

def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    check_source(ROOT)
    name = original.build_wheel(wheel_directory, config_settings, metadata_directory)
    target = Path(wheel_directory) / name
    try:
        check_asset(ROOT, target)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return name

def build_sdist(sdist_directory, config_settings=None):
    check_source(ROOT)
    name = original.build_sdist(sdist_directory, config_settings)
    target = Path(sdist_directory) / name
    try:
        check_sdist(ROOT, target)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return name
