"""Resolve private local storage or isolated temporary public demo storage."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile
from uuid import uuid4

import streamlit as st


def is_public_demo() -> bool:
    return os.getenv("QUANTEDGE_PUBLIC_DEMO", "0").strip().lower() in {"1", "true", "yes"}


def workspace_path() -> str:
    if is_public_demo():
        key = "_qe_demo_workspace_id"
        if key not in st.session_state:
            st.session_state[key] = uuid4().hex
        session_id = str(st.session_state[key])
        return str(Path(tempfile.gettempdir()) / "quantedge_public_demo" / session_id / "workspace.sqlite")
    return os.getenv("QUANTEDGE_WORKSPACE_DB", ".data/workspace.db")
