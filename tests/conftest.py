import os
import shutil
from pathlib import Path

import pytest

from platypod_pipeline.config import Settings

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def project(tmp_path):
    """A scratch copy of the project tree so generate/drift tests never touch the repo."""
    dest = tmp_path / "proj"
    shutil.copytree(ROOT, dest, ignore=shutil.ignore_patterns(".venv", ".git", "__pycache__", "*.egg-info", "target"))
    os.environ["FINANCE_ROOT"] = str(dest)
    yield Settings()
    os.environ.pop("FINANCE_ROOT", None)


def pytest_collection_modifyitems(config, items):
    if os.environ.get("FINANCE_PG_HOST"):
        return
    skip = pytest.mark.skip(reason="set FINANCE_PG_HOST (+ credentials) to run integration tests")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)
