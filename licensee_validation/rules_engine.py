# licensee_validation/rules_engine.py
"""
Config-driven business rules engine.
Determines the STATUS of a licensee record and computes derived dates.

Supported status_rule values (from states_config.json):
  - "date_based"    : compare expiration_date with today
  - "year_end_expiry": expiry = Dec 31 of issue year (Kansas)
  - "header_period" : expiry = June 30 of period year (Kentucky, Rhode Island)
"""

import logging
from datetime import date
from typing import Optional

from .normalizer import (
    parse_date,
    compute_year_end_expiry,
    compute_period_expiry,
    extract_period_year_from_header,
)

logger = logging.getLogger(__name__)


def compute_status(expiration_date_str: Optional[str]) -> str:
    """
    Compare expiration date string (YYYY-MM-DD) with today's date.
    Returns 'Active', 'Expired', or 'Unknown'.
    """
    if not expiration_date_str:
        return "Unknown"
    try:
        exp = date.fromisoformat(expiration_date_str)
        return "Active" if exp >= date.today() else "Expired"
    except ValueError:
        return "Unknown"


def apply_status_rule(record_dict: dict, state_cfg: dict,
                      period_year: Optional[int] = None) -> dict:
    """
    Mutate *record_dict* in-place:
      1. Derive expiration_date when it is implicit (year_end_expiry, header_period).
      2. Set status using the computed / existing expiration_date.

    Parameters
    ----------
    record_dict  : mutable dict with canonical fields
    state_cfg    : the state's config block from states_config.json
    period_year  : for header_period rules — the year extracted from PDF header text
    """
    rule = state_cfg.get("status_rule", "date_based")

    # ── 1. Derive expiration_date if not yet present ──────────────────────────
    if rule == "year_end_expiry":
        month = state_cfg.get("expiry_month", 12)
        day = state_cfg.get("expiry_day", 31)
        raw_issue = record_dict.get("issue_date")
        record_dict["expiration_date"] = compute_year_end_expiry(raw_issue, month, day)

    elif rule == "header_period":
        month = state_cfg.get("expiry_month", 6)
        day = state_cfg.get("expiry_day", 30)
        if period_year:
            record_dict["expiration_date"] = compute_period_expiry(period_year, month, day)
        else:
            logger.warning(
                "header_period rule requested but period_year is None "
                "for state %r — expiration_date will be None",
                state_cfg.get("name", "?"),
            )
            record_dict["expiration_date"] = None

    # "date_based" — expiration_date already mapped from the source column; nothing to derive.

    # ── 2. Compute status ─────────────────────────────────────────────────────
    record_dict["status"] = compute_status(record_dict.get("expiration_date"))

    return record_dict
