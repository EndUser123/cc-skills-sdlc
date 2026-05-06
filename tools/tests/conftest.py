"""pytest conftest for migrate_to_ef tests."""

import re
import shutil
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = _ROOT / "skills"
ENFORCE_CONFIGS_PATH = _ROOT / "enforce" / "configs" / "__init__.py"


def _clean_ef_artifacts() -> None:
    """Remove all -ef skill dirs and config entries."""
    # Remove -ef skill directories
    for skill_dir in SKILLS_DIR.iterdir():
        if skill_dir.is_dir() and skill_dir.name.endswith("-ef"):
            shutil.rmtree(skill_dir)
    # Remove -ef config entries from ENFORCE_CONFIGS
    if ENFORCE_CONFIGS_PATH.is_file():
        text = ENFORCE_CONFIGS_PATH.read_text()
        # Remove "Entry created by migrate_to_ef.py" style entries
        text = re.sub(r'\n    # Entry created by migrate_to_ef\.py\n    "[^"]+": [^\]]+\],', '', text)
        # Remove bare -ef entries (any skill ending in -ef)
        text = re.sub(r'\n    "[^"]+-ef": [^\]]+\],', '', text)
        ENFORCE_CONFIGS_PATH.write_text(text)


@pytest.fixture(autouse=True)
def clean_migrated_skills():
    """Remove any migrated -ef skills before and after each test."""
    _clean_ef_artifacts()
    yield
    _clean_ef_artifacts()
