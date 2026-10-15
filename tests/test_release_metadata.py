"""Release consistency and single Streamlit entrypoint."""
from pathlib import Path
import tomllib
import stockmarket

def test_current_version_metadata_matches():
    with Path("pyproject.toml").open("rb") as file:
        assert tomllib.load(file)["project"]["version"] == "2.1.1"
    assert stockmarket.__version__ == "2.1.1"

def test_single_streamlit_product_release_assets():
    for path in ["app.py","workspace_worker.py","RELEASE_NOTES_v2.1.1.md",
                 "docs/PRODUCT_SPEC.md","docs/STREAMLIT_WEBSITE_TUTORIAL.md",
                 "scripts/verify_features.py",
                 ".github/workflows/release-v2.yml"]:
        assert Path(path).exists()
    assert not Path("streamlit_app.py").exists()
    assert not Path("StockMarketAnalyzer.py").exists()
    assert not Path("paper_worker.py").exists()
