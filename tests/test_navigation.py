"""No duplicate ML dashboards or compulsory AI portfolio onboarding."""
from pathlib import Path
from stockmarket.ui.app import navigation_pages


def test_nav_has_focused_tradingview_workflow(monkeypatch):
    nav=navigation_pages()
    assert list(nav)==["Workspace","Strategy Lab","Paper Practice","System"]
    page_count=sum(len(pages) for pages in nav.values())
    assert page_count==13
    src=Path("src/stockmarket/ui/app.py").read_text()
    for name in ["personal_dashboard_page","chart_terminal_page",
                 "strategy_builder_page","strategy_backtesting_page",
                 "manual_paper_page","strategy_paper_page","alert_center_page"]:
        assert name in src
    assert "ai_trader_page" not in src
    assert "render_onboarding" not in src
