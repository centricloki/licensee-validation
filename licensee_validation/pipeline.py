# licensee_validation/pipeline.py
"""
Pipeline orchestrator.

Responsibilities:
  1. Load states_config.json
  2. Discover state data files under distributors/
  3. Route each file to the correct parser (Excel/CSV or PDF)
  4. Collect all LicenseeRecord objects
  5. Write output CSV + JSON to /output/
  6. Move failed files to /quarantine/

Usage (internal):
  from licensee_validation.pipeline import Pipeline
  p = Pipeline("states_config.json")
  p.run(states=["Delaware", "Kansas"])  # or None for all
"""

import json
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import pandas as pd

from .models import LicenseeRecord
from .parsers.excel_csv_parser import ExcelCsvParser
from .parsers.pdf_parser import PdfParser

logger = logging.getLogger(__name__)


class Pipeline:
    def __init__(self, config_path: str = "states_config.json"):
        self.config = self._load_config(config_path)
        self.distributors_dir = Path(self.config.get("distributors_dir", "distributors"))
        self.output_dir = Path(self.config.get("output_dir", "output"))
        self.quarantine_dir = Path(self.config.get("quarantine_dir", "quarantine"))

        # Ensure directories exist
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)

    # ── Public API ────────────────────────────────────────────────────────────

    def run(self, states: Optional[List[str]] = None,
            output_formats: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Run the full parsing pipeline.

        Parameters
        ----------
        states : list of state names to process, or None for all configured states
        output_formats : list of 'csv' / 'json' (default: both)

        Returns
        -------
        DataFrame with all parsed records in canonical schema
        """
        output_formats = output_formats or ["csv", "json"]
        states_cfg = self.config.get("states", {})
        target_states = states if states else list(states_cfg.keys())

        all_records: List[LicenseeRecord] = []

        for state_name in target_states:
            if state_name not in states_cfg:
                logger.warning("State %r not found in config — skipping.", state_name)
                continue

            state_records = self._process_state(state_name, states_cfg[state_name])
            all_records.extend(state_records)

        logger.info("Total records parsed across all states: %d", len(all_records))

        df = self._to_dataframe(all_records)
        self._write_output(df, output_formats)
        return df

    # ── State-level processing ────────────────────────────────────────────────

    def _process_state(self, state_name: str, state_cfg: dict) -> List[LicenseeRecord]:
        """Discover files for a state and parse each one."""
        records: List[LicenseeRecord] = []
        state_dir = self.distributors_dir / state_name

        if not state_dir.exists():
            logger.warning("[%s] Directory not found: %s — skipping.", state_name, state_dir)
            return records

        files = self._discover_files(state_dir, state_cfg)
        if not files:
            logger.warning("[%s] No matching files found in %s", state_name, state_dir)
            return records

        # Inject state name into config for logging inside rules_engine
        state_cfg = dict(state_cfg)
        state_cfg["name"] = state_name

        for file_path in files:
            file_records = self._parse_file(file_path, state_name, state_cfg)
            records.extend(file_records)

        logger.info("[%s] == Total: %d records", state_name, len(records))
        return records

    def _discover_files(self, state_dir: Path, state_cfg: dict) -> List[Path]:
        """Return all files matching the configured file_pattern in the state directory."""
        pattern = state_cfg.get("file_pattern", "*")
        files = sorted(state_dir.glob(pattern))
        logger.info("Discovered %d file(s) in %s matching %r", len(files), state_dir, pattern)
        return files

    def _parse_file(self, file_path: Path, state_name: str,
                    state_cfg: dict) -> List[LicenseeRecord]:
        """Route file to the correct parser and handle file-level errors."""
        file_type = state_cfg.get("file_type", "").lower()

        try:
            parser = self._get_parser(state_name, state_cfg, file_type)
            records = parser.parse(str(file_path))
            logger.info("[%s] [OK] %s -> %d records", state_name, file_path.name, len(records))
            return records
        except Exception as exc:
            logger.error(
                "[%s] ✘ File-level error for %s: %s — moving to quarantine.",
                state_name, file_path.name, exc,
            )
            self._quarantine(file_path, state_name)
            return []

    def _get_parser(self, state_name: str, state_cfg: dict, file_type: str):
        """Instantiate the appropriate parser based on file_type."""
        if file_type == "pdf":
            return PdfParser(state_name, state_cfg)
        elif file_type in ("excel", "csv"):
            return ExcelCsvParser(state_name, state_cfg)
        else:
            raise ValueError(
                f"[{state_name}] Unknown file_type {file_type!r} in config."
            )

    # ── Quarantine ────────────────────────────────────────────────────────────

    def _quarantine(self, file_path: Path, state_name: str) -> None:
        """Move a failed file to the quarantine directory."""
        dest_dir = self.quarantine_dir / state_name
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / file_path.name
        try:
            shutil.copy2(str(file_path), str(dest))
            logger.warning("[%s] Quarantined: %s → %s", state_name, file_path.name, dest)
        except Exception as exc:
            logger.error("[%s] Could not quarantine %s: %s", state_name, file_path.name, exc)

    # ── Output ────────────────────────────────────────────────────────────────

    def _to_dataframe(self, records: List[LicenseeRecord]) -> pd.DataFrame:
        """Convert list of LicenseeRecord to DataFrame in canonical column order."""
        canonical = self.config.get("canonical_schema", [])
        if not records:
            return pd.DataFrame(columns=canonical)

        data = [r.to_dict() for r in records]
        df = pd.DataFrame(data)

        # Ensure all canonical columns present, in order
        for col in canonical:
            if col not in df.columns:
                df[col] = ""
        extra_cols = [c for c in df.columns if c not in canonical]
        return df[canonical + extra_cols]

    def _write_output(self, df: pd.DataFrame, formats: List[str]) -> None:
        """Write the master output file(s) to /output/."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        base_name = "master_tobacco_licenses"

        if "csv" in formats:
            csv_path = self.output_dir / f"{base_name}.csv"
            df.to_csv(csv_path, index=False, encoding="utf-8-sig")
            logger.info("Output CSV written: %s (%d rows)", csv_path, len(df))

        if "json" in formats:
            json_path = self.output_dir / f"{base_name}.json"
            df.to_json(json_path, orient="records", indent=2, force_ascii=False)
            logger.info("Output JSON written: %s (%d rows)", json_path, len(df))

    # ── Config loader ─────────────────────────────────────────────────────────

    @staticmethod
    def _load_config(config_path: str) -> dict:
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found: {config_path!r}")
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
