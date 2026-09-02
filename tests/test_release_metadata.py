from __future__ import annotations

from pathlib import Path
import tomllib

import stockmarket
from stockmarket.ui.research_lab import research_lab_page


def test_v1_release_versions_are_synchronized() -> None:
    with Path("pyproject.toml").open("rb") as handle:
        project = tomllib.load(handle)["project"]
    assert project["version"] == "1.0.0"
    assert stockmarket.__version__ == "1.0.0"


def test_v1_release_assets_exist() -> None:
    assert Path("RELEASE_NOTES_v1.0.md").is_file()
    assert Path(".github/workflows/release-v1.yml").is_file()
    assert callable(research_lab_page)
