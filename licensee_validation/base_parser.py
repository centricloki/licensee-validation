# licensee_validation/base_parser.py
"""
Abstract base class that every state parser must implement.
Provides shared helpers for column mapping, record construction, and logging.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List, Optional

from .models import LicenseeRecord
from .normalizer import clean_str, clean_zip, parse_date
from .rules_engine import apply_status_rule, extract_period_year_from_header

logger = logging.getLogger(__name__)


class BaseParser(ABC):
    """
    All state parsers inherit from this class.
    Subclasses must implement `parse()`.
    """

    def __init__(self, state_name: str, state_cfg: dict):
        self.state_name = state_name
        self.state_cfg = state_cfg
        self.column_map: dict = state_cfg.get("column_map", {})

    # ── Abstract interface ────────────────────────────────────────────────────

    @abstractmethod
    def parse(self, file_path: str) -> List[LicenseeRecord]:
        """
        Parse *file_path* and return a list of LicenseeRecord objects.
        Implementations must catch per-row exceptions and log warnings
        rather than re-raising.
        """
        ...

    # ── Shared helpers ────────────────────────────────────────────────────────

    def _now_utc(self) -> str:
        """ISO-8601 UTC timestamp for the parsed_at field."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _map_row(self, raw: dict, source_file: str,
                 period_year: Optional[int] = None) -> Optional[LicenseeRecord]:
        """
        Apply column_map to *raw* dict, build a LicenseeRecord, apply
        status rules, and return the record.  Returns None if license_number
        is empty after cleaning (row-level drop rule).
        """
        mapped: dict = {
            "state": self.state_name,
            "license_number": "",
            "legal_name": "",
            "dba": "",
            "address": "",
            "city": "",
            "state_code": "",
            "zip": "",
            "issue_date": None,
            "expiration_date": None,
            "status": "Unknown",
            "license_type": "",
            "source_file_name": source_file,
            "parsed_at": self._now_utc(),
        }

        for raw_col, canonical_col in self.column_map.items():
            value = raw.get(raw_col)
            if value is None:
                continue

            if canonical_col in ("issue_date", "expiration_date"):
                mapped[canonical_col] = parse_date(value, canonical_col)
            elif canonical_col == "zip":
                mapped["zip"] = clean_zip(value)
            else:
                mapped[canonical_col] = clean_str(value)

        # ── Composite license key fallback ─────────────────────────────────────
        # Used by states without an explicit license number column (e.g. WI, RI)
        if not mapped["license_number"]:
            composite_fields = self.state_cfg.get("composite_license_key_fields", [])
            if composite_fields:
                parts = [clean_str(raw.get(f, "")) for f in composite_fields]
                composite = "-".join(p for p in parts if p)
                if composite:
                    mapped["license_number"] = composite

        # ── Row-level drop: skip rows without a license number ─────────────────
        if not mapped["license_number"]:
            logger.warning(
                "[%s] Skipping row - empty license_number. Row: %s",
                self.state_name,
                {k: raw.get(k, "") for k in list(self.column_map.keys())[:3]},
            )
            return None

        # ── Apply business rules (status + derived expiry) ─────────────────────
        mapped = apply_status_rule(mapped, self.state_cfg, period_year=period_year)

        # ── Strip non-canonical fields before constructing dataclass ───────────
        # Extra fields (e.g. county, agent_name, last_updated) from column_map
        # that map to non-dataclass keys must be removed to avoid TypeError.
        canonical_fields = {f.name for f in LicenseeRecord.__dataclass_fields__.values()}
        mapped = {k: v for k, v in mapped.items() if k in canonical_fields}

        return LicenseeRecord(**mapped)

    def _apply_filter(self, df, filter_cfg: dict):
        """
        Apply an optional row-filter from config:
          { "column": "Business Activity", "contains": "TOBACCO" }
        Returns filtered DataFrame.
        """
        if not filter_cfg:
            return df
        col = filter_cfg.get("column", "")
        contains = filter_cfg.get("contains", "")
        if col not in df.columns:
            logger.warning(
                "[%s] Filter column %r not found in file. Skipping filter.",
                self.state_name, col
            )
            return df
        mask = df[col].astype(str).str.contains(contains, case=False, na=False)
        filtered = df[mask]
        logger.info(
            "[%s] Filter '%s contains %s': %d → %d rows",
            self.state_name, col, contains, len(df), len(filtered)
        )
        return filtered
