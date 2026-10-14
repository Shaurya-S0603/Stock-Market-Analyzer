"""Optional, explicit-fetch public company facts/news. Never manufacture unavailable fields."""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from urllib.parse import urlparse

from .database import clean_symbol

PROFILE_KEYS = {
    "longName": "Company", "shortName": "Short name", "exchange": "Exchange",
    "sector": "Sector", "industry": "Industry", "country": "Country",
    "currency": "Currency", "website": "Website", "longBusinessSummary": "Description",
}
FUNDAMENTAL_KEYS = {
    "marketCap": "Market capitalization", "trailingPE": "Trailing P/E",
    "forwardPE": "Forward P/E", "trailingEps": "EPS", "totalRevenue": "Revenue",
    "revenueGrowth": "Revenue growth", "profitMargins": "Profit margin",
    "debtToEquity": "Debt/equity", "returnOnEquity": "Return on equity",
    "dividendYield": "Dividend yield", "freeCashflow": "Free cash flow",
    "bookValue": "Book value",
}


def _safe_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlparse(value)
    return value if parsed.scheme in {"https", "http"} and parsed.netloc else None


def _clean_value(value: object) -> str | float | int | None:
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, (float, int)) and not isinstance(value, bool) and isfinite(float(value)):
        return value
    return None


def _extract_news(item: dict) -> dict | None:
    if not isinstance(item, dict):
        return None
    content = item.get("content") or item
    if not isinstance(content, dict):
        return None
    title = content.get("title") or item.get("title")
    publisher = content.get("provider") or content.get("publisher") or item.get("publisher")
    if isinstance(publisher, dict):
        publisher = publisher.get("displayName") or publisher.get("name")
    link = (content.get("canonicalUrl") or content.get("clickThroughUrl"))
    if isinstance(link, dict):
        link = link.get("url")
    link = _safe_url(link) or _safe_url(item.get("link"))
    if not isinstance(title, str) or not title.strip() or link is None:
        return None
    moment = content.get("pubDate") or item.get("providerPublishTime")
    if isinstance(moment, (float, int)):
        moment = datetime.fromtimestamp(moment, tz=timezone.utc).isoformat()
    if not isinstance(moment, str):
        moment = "Publication time unavailable"
    return {"Title": title.strip(), "Source": str(publisher or "Source unavailable"),
            "Published": moment, "URL": link}


def fetch_company_research(symbol: str, *, ticker_factory=None) -> dict:
    """Fetch on demand; each failing field/category is explicitly reported."""
    clean = clean_symbol(symbol)
    if ticker_factory is None:
        import yfinance as yf
        ticker_factory = yf.Ticker
    try:
        ticker = ticker_factory(clean)
    except Exception as exc:
        return {"symbol": clean, "profile": {}, "fundamentals": {}, "news": [],
                "warnings": ["Provider initialization failed: " + str(exc)]}
    warnings = []
    info = {}
    try:
        data = ticker.info
        if isinstance(data, dict):
            info = data
        else:
            warnings.append("Company information is not available")
    except Exception as exc:
        warnings.append("Company information unavailable: " + str(exc))
    profile = {label: value for key, label in PROFILE_KEYS.items()
               if (value := _clean_value(info.get(key))) is not None}
    fundamentals = {label: value for key, label in FUNDAMENTAL_KEYS.items()
                    if (value := _clean_value(info.get(key))) is not None}
    if "Website" in profile and not _safe_url(profile["Website"]):
        profile.pop("Website")
    news = []
    try:
        raw = ticker.news
        if isinstance(raw, list):
            news = [article for entry in raw[:20] if (article := _extract_news(entry)) is not None]
        else:
            warnings.append("News is unavailable for this symbol")
    except Exception as exc:
        warnings.append("News unavailable: " + str(exc))
    if not profile:
        warnings.append("No company profile fields supplied by this provider")
    if not fundamentals:
        warnings.append("No supported fundamental fields supplied by this provider")
    return {"symbol": clean, "profile": profile, "fundamentals": fundamentals,
            "news": news[:12], "warnings": warnings}
