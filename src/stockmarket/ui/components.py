from __future__ import annotations

from html import escape
from typing import Iterable

import streamlit as st


def page_header(title: str, subtitle: str, eyebrow: str = "MARKET INTELLIGENCE", meta: str | None = None) -> None:
    meta_html = f'<div class="qe-meta">{escape(meta)}</div>' if meta else ""
    st.markdown(
        f"""
        <div class="qe-page-head">
          <div>
            <div class="qe-eyebrow">{escape(eyebrow)}</div>
            <h1 class="qe-title">{escape(title)}</h1>
            <p class="qe-subtitle">{escape(subtitle)}</p>
          </div>
          {meta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_header(title: str, note: str | None = None) -> None:
    note_html = f'<span class="qe-section-note">{escape(note)}</span>' if note else ""
    st.markdown(f'<div class="qe-section-head"><div class="qe-section-title">{escape(title)}</div>{note_html}</div>', unsafe_allow_html=True)


def kpi_card(label: str, value: str, delta: str = "", tone: str = "blue", icon: str = "•") -> None:
    tone_class = {"positive": "qe-positive", "negative": "qe-negative", "warning": "qe-warning", "blue": "qe-blue"}.get(tone, "qe-blue")
    delta_html = f'<div class="qe-kpi-delta {tone_class}">{escape(delta)}</div>' if delta else '<div class="qe-kpi-delta">&nbsp;</div>'
    st.markdown(
        f"""<div class="qe-kpi"><div class="qe-kpi-top"><div class="qe-kpi-label">{escape(label)}</div><div class="qe-kpi-icon" aria-hidden="true">{escape(icon)}</div></div><div class="qe-kpi-value">{escape(value)}</div>{delta_html}</div>""",
        unsafe_allow_html=True,
    )


def status_badge(label: str, state: str = "neutral") -> str:
    cls = {"active": "active", "warning": "warn", "danger": "danger"}.get(state, "")
    return f'<span class="qe-status {cls}"><span class="qe-dot"></span>{escape(label)}</span>'


def callout(title: str, body: str) -> None:
    st.markdown(f'<div class="qe-callout"><strong>{escape(title)}</strong><br>{escape(body)}</div>', unsafe_allow_html=True)


def kpi_grid(cards: Iterable[dict[str, str]], columns: int = 4) -> None:
    card_list = list(cards)
    for start in range(0, len(card_list), columns):
        row = st.columns(min(columns, len(card_list) - start))
        for column, card in zip(row, card_list[start : start + columns]):
            with column:
                kpi_card(**card)
