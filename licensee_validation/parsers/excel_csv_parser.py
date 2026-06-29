# licensee_validation/parsers/excel_csv_parser.py
"""
Generic parser for Excel (.xlsx) and CSV (.csv) tobacco license files.

Handles:
  - Delaware   (Excel, filter on Business Activity)
  - District of Columbia (CSV, filter on BUSINESSACTIVITY)
  - Kansas     (CSV, no expiry column → year-end rule)
  - Pennsylvania (Excel)
  - Washington (Excel)
  - Wisconsin  (CSV)

All logic beyond reading/filtering/mapping is driven by states_config.json
via the BaseParser helpers.
"""

import logging
import os
from typing import List

import pandas as pd

from ..base_parser import BaseParser
from ..models import LicenseeRecord

logger = logging.getLogger(__name__)


class ExcelCsvParser(BaseParser):
    """Parses Excel and CSV files into LicenseeRecord instances."""

    def parse(self, file_path: str) -> List[LicenseeRecord]:
        records: List[LicenseeRecord] = []
        ext = os.path.splitext(file_path)[1].lower()
        source_name = os.path.basename(file_path)

        logger.info("[%s] Reading %s file: %s", self.state_name, ext.upper(), file_path)

        try:
            df = self._load_file(file_path, ext)
        except Exception as exc:
            logger.error(
                "[%s] Failed to load file %r: %s", self.state_name, file_path, exc
            )
            raise  # Re-raise so pipeline can quarantine this file

        # ── Optional row-filter from config ───────────────────────────────────
        filter_cfg = self.state_cfg.get("filter")
        if filter_cfg:
            df = self._apply_filter(df, filter_cfg)

        logger.info("[%s] Processing %d rows from %s", self.state_name, len(df), source_name)

        for idx, row in df.iterrows():
            try:
                raw = {col: row[col] for col in df.columns}
                record = self._map_row(raw, source_name)
                if record:
                    records.append(record)
            except Exception as exc:
                logger.warning(
                    "[%s] Row %d skipped due to error: %s", self.state_name, idx, exc
                )

        logger.info(
            "[%s] Parsed %d valid records from %s", self.state_name, len(records), source_name
        )
        return records

    # ── Private helpers ───────────────────────────────────────────────────────

    def _load_file(self, file_path: str, ext: str) -> pd.DataFrame:
        """
        Load file into a single DataFrame.
        For Excel: merges all sheets.
        For CSV: tries UTF-8, falls back to latin-1 encoding.
        """
        if ext in (".xlsx", ".xls"):
            sheets = pd.read_excel(file_path, sheet_name=None, dtype=str)
            frames = []
            for sheet_name, sheet_df in sheets.items():
                logger.info(
                    "[%s] Sheet %r has %d rows", self.state_name, sheet_name, len(sheet_df)
                )
                # Drop fully-empty rows
                sheet_df = sheet_df.dropna(how="all")
                frames.append(sheet_df)
            df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        elif ext == ".csv":
            df = self._read_csv_safe(file_path)
        else:
            raise ValueError(f"Unsupported file extension: {ext!r}")

        # Strip column name whitespace
        df.columns = [str(c).strip() for c in df.columns]
        return df

    def _read_csv_safe(self, file_path: str) -> pd.DataFrame:
        """Try multiple encodings for CSV files."""
        for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
            try:
                df = pd.read_csv(file_path, dtype=str, encoding=encoding, low_memory=False)
                logger.info("[%s] CSV loaded with encoding=%r", self.state_name, encoding)
                return df
            except UnicodeDecodeError:
                continue
        raise ValueError(f"Could not decode CSV {file_path!r} with any known encoding.")
