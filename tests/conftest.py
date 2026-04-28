import pytest
from pathlib import Path

@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    (tmp_path / "templates").mkdir()
    (tmp_path / "jobs").mkdir()
    return tmp_path
