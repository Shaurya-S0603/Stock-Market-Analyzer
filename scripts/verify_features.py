"""Produce machine-readable CI evidence from executed JUnit tests; fail on missing coverage."""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from xml.etree import ElementTree

REQUIRED = {
    "startup_and_navigation": ["test_app_startup", "test_navigation", "test_phase5_management_page"],
    "market_data_and_watchlists": ["test_workspace_phase1", "test_data_defaults"],
    "charts_and_indicators": ["test_workspace_indicators", "test_workspace_charts_research"],
    "company_research_and_screening": ["test_workspace_research_storage", "test_workspace_pages"],
    "strategies_and_backtest_accounting": [
        "test_workspace_strategy_schema", "test_workspace_strategy_backtest", "test_workspace_strategy_integration"],
    "saved_strategy_versions_and_comparison": ["test_workspace_strategy_repository", "test_workspace_strategy_pages"],
    "strategy_paper_accounts": ["test_workspace_phase4_paper", "test_workspace_phase4_pages"],
    "alert_and_monitoring_worker": ["test_workspace_phase4_alerts", "test_workspace_phase4_pages"],
    "sqlite_backup_and_recovery": ["test_phase5_portability"],
    "ohlcv_import_export": ["test_phase5_csv"],
    "ai_trader_and_legacy_paper_risk": [
        "test_ai_trader_quantity", "test_return_seeking_trader", "test_research_intelligence",
        "test_persistent_simulation", "test_adaptive_exits"],
    "research_models_and_validation": [
        "test_calibration", "test_drift", "test_experiment_registry",
        "test_ensemble_benchmarks", "test_portfolio_backtest"],
}

def verify(xml_path: Path, output: Path) -> dict:
    cases = list(ElementTree.parse(xml_path).getroot().iter("testcase"))
    if not cases:
        raise RuntimeError("No test cases found")
    classified = defaultdict(list)
    for case in cases:
        module = str(case.attrib.get("classname", "")).rsplit(".", 1)[-1]
        classified[module].append({
            "name": case.attrib.get("name", ""),
            "passed": not case.findall("failure") and not case.findall("error") and not case.findall("skipped"),
            "failed": bool(case.findall("failure") or case.findall("error")),
            "skipped": bool(case.findall("skipped")),
        })
    features = {}
    for category, modules in REQUIRED.items():
        tests = [item for module in modules for item in classified[module]]
        missing = [module for module in modules if not classified[module]]
        count_passed = sum(bool(test["passed"]) for test in tests)
        features[category] = {
            "status": "PASS" if not missing and count_passed == len(tests) else "FAIL",
            "tests": len(tests),
            "passed": count_passed,
            "missing_required_test_modules": missing,
            "required_test_modules": modules,
        }
    failed = sum(bool(case.findall("failure") or case.findall("error")) for case in cases)
    skipped = sum(bool(case.findall("skipped")) for case in cases)
    result = {
        "project": "QuantEdge 2.0",
        "evidence_type": "Executed pytest JUnit XML from GitHub Actions",
        "utc_generated": datetime.now(timezone.utc).isoformat(),
        "commit_sha": os.getenv("GITHUB_SHA", "local"),
        "python_version": sys.version.split()[0],
        "total_tests": len(cases),
        "failed_tests": failed,
        "skipped_tests": skipped,
        "features": features,
        "overall": "PASS" if not failed and not skipped and all(
            v["status"] == "PASS" for v in features.values()) else "FAIL",
        "not_verified": [
            "A deployed cloud URL or physical browser/mobile device",
            "Real-time third-party market-data correctness",
            "24/7 worker availability or external push alerts",
            "Actual brokerage execution or financial profits",
            "All conceivable combinations of user strategies",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    if result["overall"] != "PASS":
        raise RuntimeError("Feature evidence contains failures or missing required module tests")
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("junit_xml", type=Path)
    parser.add_argument("--output", type=Path, default=Path("artifacts/feature_evidence.json"))
    args = parser.parse_args()
    result = verify(args.junit_xml, args.output)
    print("Phase 5 automated verification:", result["overall"], result["total_tests"], "tests in",
          len(result["features"]), "feature areas")
