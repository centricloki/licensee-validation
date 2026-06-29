# licensee_validation/normalizer.py
"""
Field normalization utilities:
 - Date parsing / formatting  (YYYY-MM-DD canonical form)
 - String cleaning (strip, upper, None-guarding)
 - Derived expiration date computations (year-end, header-period)
"""

import re
import logging
from datetime import date, datetime
from typing import Optional

from dateutil import parser as dateutil_parser

logger = logging.getLogger(__name__)

# ── Date normalization ────────────────────────────────────────────────────────

_CANONICAL_FMT = "%Y-%m-%d"


def parse_date(value, field_name: str = "") -> Optional[str]:
    """
    Attempt to parse *value* into a YYYY-MM-DD string.
    Returns None on failure; logs a WARNING per field.
    """
    if value is None:
        return None

    # Already a Python date / datetime object (pandas Timestamp, etc.)
    if isinstance(value, (date, datetime)):
        try:
            return value.strftime(_CANONICAL_FMT)
        except Exception:
            return None

    raw = str(value).strip()
    if not raw or raw.lower() in {"nan", "none", "nat", "n/a", "", "0"}:
        return None

    try:
        parsed = dateutil_parser.parse(raw, dayfirst=False)
        return parsed.strftime(_CANONICAL_FMT)
    except Exception:
        logger.warning("Could not parse date value %r for field %r", raw, field_name)
        return None


def compute_year_end_expiry(issue_date_str: Optional[str],
                             month: int = 12,
                             day: int = 31) -> Optional[str]:
    """
    Given an issue date string, derive expiration = MM/DD/<same year>.
    Used by Kansas (licenses expire Dec 31 of issue year).
    """
    if not issue_date_str:
        return None
    try:
        year = dateutil_parser.parse(issue_date_str).year
        return date(year, month, day).strftime(_CANONICAL_FMT)
    except Exception:
        logger.warning("compute_year_end_expiry failed for %r", issue_date_str)
        return None


def compute_period_expiry(year: int, month: int = 6, day: int = 30) -> str:
    """
    Build an explicit expiration date from a known year/month/day.
    Used by Kentucky and Rhode Island (June 30 of the license period year).
    """
    return date(year, month, day).strftime(_CANONICAL_FMT)


def extract_period_year_from_header(header_text: str) -> Optional[int]:
    """
    Scan header text for patterns like:
      'License Period July 1, 2025 through June 30, 2026'
      '07/01/2025 - 06/30/2026'
    Returns the *ending* year (the expiry year).
    """
    # Pattern: 4-digit year, grab the last occurrence (end-year)
    years = re.findall(r"\b(20\d{2})\b", header_text)
    if years:
        return int(years[-1])
    return None


# ── String cleaning ───────────────────────────────────────────────────────────

def clean_str(value) -> str:
    """Strip, collapse whitespace, return empty string for null-like values."""
    if value is None:
        return ""
    s = str(value).strip()
    if s.lower() in {"nan", "none", "nat", "n/a"}:
        return ""
    # Collapse internal whitespace
    return re.sub(r"\s+", " ", s)


def clean_zip(value) -> str:
    """Normalize zip: keep only digits and leading zeros; truncate to 5."""
    raw = clean_str(value)
    digits = re.sub(r"[^0-9]", "", raw)
    return digits[:5] if digits else ""
