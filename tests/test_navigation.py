from __future__ import annotations

from stockmarket.ui.app import _build_navigation_pages


def test_navigation_pages_have_unique_stable_routes() -> None:
    pages = _build_navigation_pages(object())
    flat_pages = [page for section in pages.values() for page in section]
    routes = [page.url_path for page in flat_pages]

    assert routes == [
        "",
        "markets",
        "ai-trader",
        "portfolio",
        "trade-journal",
        "model-analytics",
        "backtesting",
        "risk-analytics",
        "settings",
    ]
    assert len(routes) == len(set(routes))
