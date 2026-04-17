"""Shared fixtures."""

from pathlib import Path

import pytest

from agnes.config.settings import Settings
from agnes.data.db_loader import get_engine


@pytest.fixture
def db_path() -> Path:
    root = Path(__file__).resolve().parents[1]
    return root / "data" / "raw" / "db.sqlite"


@pytest.fixture
def engine(db_path: Path):
    if not db_path.is_file():
        pytest.skip(f"Database not found: {db_path}")
    return get_engine(Settings(db_path=db_path))
