from __future__ import annotations

from pathlib import Path
import tomllib

import stockmarket
from stockmarket.ui.research_lab import research_lab_page


def test_release_versions_are_synchronized() -> None:
    with Path("pyproject.toml").open("rb") as handle:
        project = tomllib.load(handle)["project"]
    assert project["version"] == "2.0.0"
    assert stockmarket.__version__ == "2.0.0"


def test_all_release_assets_exist() -> None:
    assert Path("RELEASE_NOTES_v1.0.md").is_file()
    assert Path("RELEASE_NOTES_v1.0.1.md").is_file()
    assert Path("RELEASE_NOTES_v1.1.0.md").is_file()
    assert Path("RESEARCH_FOUNDATIONS.md").is_file()
    assert Path(".github/workflows/release-v1.yml").is_file()
    assert callable(research_lab_page)


def test_v2_release_assets_and_feature_evidence_entrypoint():
    assert Path("RELEASE_NOTES_v2.0.0.md").exists()
    assert Path(".github/workflows/release-v2.yml").exists()
    assert Path("docs/PHASE_5_OPERATIONS.md").exists()
    assert Path("scripts/verify_features.py").exists()
