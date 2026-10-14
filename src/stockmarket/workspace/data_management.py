"""Local data portability and verification controls, available without paper onboarding."""
from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
from uuid import uuid4

import streamlit as st
from pydantic import ValidationError

from .csv_io import export_history_csv, import_history_csv
from .market_data import VALID_INTERVALS
from .portability import make_archive, inspect_archive, stage_restore
from .ui import workspace_db


def data_management_page() -> None:
    st.title("Data Management & Recovery")
    st.caption("Local-first research storage. No brokerage transfers, user logins or paid cloud dependency.")
    db = workspace_db(os.getenv("QUANTEDGE_WORKSPACE_DB", ".data/workspace.db"))
    st.info(
        "The v2 workspace and legacy AI Trader use independent SQLite files. "
        "Backup both when available. Restores are staged and NEVER replace running databases."
    )
    with st.expander("Database locations and data integrity", expanded=True):
        st.code(f"Workspace database: {Path(db.path).resolve()}")
        legacy = os.getenv("PAPER_DB_PATH", ".data/paper_trading.db")
        st.code(f"Legacy paper database: {Path(legacy).resolve()}")
        with db.engine.connect() as conn:
            health = conn.exec_driver_sql("PRAGMA integrity_check").scalar()
            foreign_keys = conn.exec_driver_sql("PRAGMA foreign_key_check").all()
            versions = conn.exec_driver_sql(
                "SELECT version FROM workspace_schema_versions ORDER BY version"
            ).scalars().all()
        st.metric("SQLite integrity", health)
        st.metric("Foreign-key violations", len(foreign_keys))
        st.caption("Workspace schema versions applied: " + ", ".join(map(str, versions)))
        if health != "ok" or foreign_keys:
            st.error("Local data integrity failed. Back up, investigate and avoid making further changes.")

    st.subheader("Backup both local databases")
    st.caption("Backups use SQLite's online snapshot API to include committed WAL changes.")
    if st.button("Create consistent backup archive"):
        try:
            st.session_state["qe_recent_backup"] = make_archive(db, legacy_path=legacy)
        except (ValueError, OSError) as exc:
            st.error(str(exc))
    archive = st.session_state.get("qe_recent_backup")
    if archive:
        st.download_button(
            "Download checksummed backup ZIP",
            archive, file_name=f"quantedge-backup-{datetime.now(timezone.utc):%Y%m%d}.zip",
            mime="application/zip",
        )
        if st.button("Clear generated archive from session memory"):
            st.session_state.pop("qe_recent_backup", None)
            st.rerun()

    st.subheader("Verify and stage a backup")
    st.warning(
        "Restoring writes into a NEW local directory. To activate restored files, "
        "stop Streamlit/worker processes, set QUANTEDGE_WORKSPACE_DB and optionally PAPER_DB_PATH "
        "to the printed paths, then restart. Nothing automatically overwrites existing portfolios."
    )
    uploaded = st.file_uploader("Choose a QuantEdge backup ZIP", type=["zip"], key="qe_restore_file")
    if uploaded is not None:
        try:
            data = uploaded.getvalue()
            validated = inspect_archive(data)
            st.success("Backup format, SQLite integrity and SHA256 checks verified")
            st.json(validated)
            if st.button("Stage verified restore to a NEW directory"):
                base = Path(db.path).resolve().parent / "recovered"
                path = base / ("quantedge-" + uuid4().hex)
                result = stage_restore(data, path)
                st.success("Restored into new directory, no active database modified.")
                st.code(
                    f"QUANTEDGE_WORKSPACE_DB={result['workspace_db']}\n"
                    + (f"PAPER_DB_PATH={result['paper_db']}\n" if result["paper_db"] else "")
                )
                st.caption("Copy these environment variables, stop the application, then restart.")
        except (ValueError, OSError, FileExistsError) as exc:
            st.error("Backup rejected: " + str(exc))

    st.subheader("Historical OHLCV CSV export / import")
    st.caption(
        "CSV requires ISO timestamps with explicit timezone offsets and validated OHLCV fields. "
        "Imports reject changed existing candles or conflicting price-provider metadata."
    )
    symbols = db.cached_symbols()
    col = st.columns(2)
    symbol = col[0].text_input("Market ticker", value=symbols[0] if symbols else "MSFT",
                               key="qe_data_symbol").strip().upper()
    interval = col[1].selectbox("Timeframe", sorted(VALID_INTERVALS), key="qe_data_interval")
    if st.button("Prepare historical CSV export"):
        try:
            st.session_state["qe_recent_history_csv"] = (
                (symbol, interval), export_history_csv(db, symbol, interval)
            )
        except (ValueError, OSError) as exc:
            st.warning(str(exc))
    export = st.session_state.get("qe_recent_history_csv")
    if export and export[0] == (symbol, interval):
        st.download_button(
            "Download original saved OHLCV and provenance",
            export[1], file_name=f"{symbol.replace('.', '_')}-{interval}.csv", mime="text/csv",
        )
    csv_file = st.file_uploader("Choose UTF-8 CSV to import into the selected ticker/timeframe",
                                type=["csv"], key="qe_history_upload")
    if csv_file is not None:
        st.warning("Import writes real historical data to the active workspace. Verify ticker and interval.")
        if st.button("Validate and import CSV"):
            try:
                info = import_history_csv(db, csv_file.getvalue(),
                                          symbol=symbol, interval=interval)
                st.success(f"Imported {info['bars_imported']} validated historical bars")
                st.json(info)
            except (ValueError, OSError) as exc:
                st.error("Import rejected: " + str(exc))

    st.caption(
        "Local storage is durable only where the filesystem is durable. "
        "Streamlit Community Cloud files may disappear after redeployment. Keep backup ZIPs privately."
    )
