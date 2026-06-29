#!/usr/bin/env python3
"""
main.py — CLI entry point for the Tobacco License Validation System
Republic Brands Compliance Tool

Commands
--------
Run full pipeline (all states):
    python main.py run

Run for specific state(s):
    python main.py run --state Delaware --state Pennsylvania

Run and output only CSV:
    python main.py run --format csv

Verify a licensee by license number:
    python main.py verify --license-number TD000567

Verify a licensee by business name (partial match):
    python main.py verify --business-name "7HILLS"

Verify with specific state filter:
    python main.py verify --business-name "Core-Mark" --state Kentucky

Show all expired licenses:
    python main.py verify --status Expired
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import pandas as pd

# Fix Windows console Unicode (cp1252 -> utf-8)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ── Logging setup (console + file) ───────────────────────────────────────────

def setup_logging(log_file: str = "execution.log", verbose: bool = False) -> None:
    """
    Configure root logger to write to both console and a log file.

    Log rotation strategy:
      - execution.log  : Always contains ONLY the latest run (truncated on start).
      - logs/execution_YYYYMMDD_HHMMSS.log : Timestamped archive of every run.
    """
    from datetime import datetime, timezone

    level = logging.DEBUG if verbose else logging.INFO

    root = logging.getLogger()
    root.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(level)
    ch.setFormatter(fmt)
    root.addHandler(ch)

    # Latest log — truncated each run so it only shows the current run
    fh_latest = logging.FileHandler(log_file, mode="w", encoding="utf-8")
    fh_latest.setLevel(logging.DEBUG)
    fh_latest.setFormatter(fmt)
    root.addHandler(fh_latest)

    # Timestamped archive log — never overwritten
    logs_dir = Path(log_file).parent / "logs"
    logs_dir.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    archive_name = logs_dir / f"execution_{ts}.log"
    fh_archive = logging.FileHandler(archive_name, mode="w", encoding="utf-8")
    fh_archive.setLevel(logging.DEBUG)
    fh_archive.setFormatter(fmt)
    root.addHandler(fh_archive)


logger = logging.getLogger(__name__)


# ── Sub-command: run ──────────────────────────────────────────────────────────

def cmd_run(args) -> None:
    """Execute the full parsing pipeline."""
    from licensee_validation.pipeline import Pipeline

    config_path = args.config
    if not os.path.exists(config_path):
        logger.error("Config file not found: %s", config_path)
        sys.exit(1)

    states = args.state if args.state else None
    formats = args.format if args.format else ["csv", "json"]

    logger.info("=" * 60)
    logger.info("Tobacco License Validation Pipeline — START")
    logger.info("Config  : %s", config_path)
    logger.info("States  : %s", states or "ALL")
    logger.info("Formats : %s", formats)
    logger.info("=" * 60)

    pipeline = Pipeline(config_path=config_path)
    df = pipeline.run(states=states, output_formats=formats)

    logger.info("=" * 60)
    logger.info("Pipeline complete. Total records: %d", len(df))
    logger.info("=" * 60)

    # Quick summary table printed to console
    if not df.empty:
        print("\n-- Summary by State --")
        summary = df.groupby(["state", "status"]).size().unstack(fill_value=0)
        print(summary.to_string())
        print()


# ── Sub-command: verify ───────────────────────────────────────────────────────

def cmd_verify(args) -> None:
    """
    Query the master output CSV/JSON to verify a license or business.
    Falls back to running the pipeline first if output doesn't exist.
    """
    import json as _json

    output_csv = Path("output") / "master_tobacco_licenses.csv"
    output_json = Path("output") / "master_tobacco_licenses.json"

    # Load existing output, or prompt user to run pipeline first
    if output_csv.exists():
        df = pd.read_csv(output_csv, dtype=str)
        logger.info("Loaded %d records from %s", len(df), output_csv)
    elif output_json.exists():
        df = pd.read_json(output_json, dtype=str)
        logger.info("Loaded %d records from %s", len(df), output_json)
    else:
        print(
            "\n⚠  No output data found. Please run the pipeline first:\n"
            "   python main.py run\n"
        )
        sys.exit(1)

    # ── Build filter mask ─────────────────────────────────────────────────────
    mask = pd.Series([True] * len(df), index=df.index)

    if args.license_number:
        query = args.license_number.strip().upper()
        mask &= df["license_number"].astype(str).str.upper().str.contains(query, na=False)
        logger.info("Filter: license_number contains %r", query)

    if args.business_name:
        query = args.business_name.strip().upper()
        mask &= (
            df["legal_name"].astype(str).str.upper().str.contains(query, na=False) |
            df["dba"].astype(str).str.upper().str.contains(query, na=False)
        )
        logger.info("Filter: business name contains %r", query)

    if args.state:
        state_filter = [s.strip() for s in args.state]
        mask &= df["state"].isin(state_filter)
        logger.info("Filter: state in %s", state_filter)

    if args.status:
        mask &= df["status"].str.lower() == args.status.lower()
        logger.info("Filter: status = %r", args.status)

    results = df[mask].copy()

    # ── Display results ───────────────────────────────────────────────────────
    if results.empty:
        print("\nNo matching records found.\n")
        return

    total = len(results)
    print(f"\nFound {total} matching record(s):")

    display_cols = [
        "state", "license_number", "legal_name", "dba",
        "address", "city", "state_code", "zip",
        "issue_date", "expiration_date", "status",
        "license_type", "source_file_name", "parsed_at",
    ]
    display_cols = [c for c in display_cols if c in results.columns]

    # Labels — human-readable field names aligned for card display
    labels = {
        "state":            "State",
        "license_number":   "License Number",
        "legal_name":       "Legal Name",
        "dba":              "DBA",
        "address":          "Address",
        "city":             "City",
        "state_code":       "State Code",
        "zip":              "ZIP",
        "issue_date":       "Issue Date",
        "expiration_date":  "Expiration Date",
        "status":           "Status",
        "license_type":     "License Type",
        "source_file_name": "Source File",
        "parsed_at":        "Parsed At",
    }
    col_w = max(len(v) for v in labels.values()) + 2  # right-align label column

    def _val(v) -> str:
        """Stringify a value, replacing NaN/None with a dash."""
        if v is None or (isinstance(v, float) and str(v) == "nan"):
            return "-"
        return str(v).strip() or "-"

    sep = "-" * 56

    for idx, (_, row) in enumerate(results.iterrows(), start=1):
        status_val = _val(row.get("status", ""))
        status_marker = {"Active": "[ACTIVE]", "Expired": "[EXPIRED]", "Unknown": "[UNKNOWN]"}.get(
            status_val, f"[{status_val}]"
        )
        print(f"\n{sep}")
        print(f"  Record {idx} of {total}  {status_marker}")
        print(sep)
        for col in display_cols:
            label = labels.get(col, col)
            value = _val(row.get(col))
            print(f"  {label:<{col_w}}: {value}")

    print(f"\n{sep}")
    print(f"  Total: {total} record(s) found")
    print(sep)

    # Optionally export results
    if args.export:
        out_path = args.export
        if out_path.endswith(".json"):
            results.to_json(out_path, orient="records", indent=2)
        else:
            results.to_csv(out_path, index=False, encoding="utf-8-sig")
        print(f"\n  Results exported to: {out_path}")


# ── Argument parser ───────────────────────────────────────────────────────────

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Republic Brands — Tobacco License Validation System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--config", default="states_config.json",
        help="Path to the states configuration JSON file (default: states_config.json)"
    )
    parser.add_argument(
        "--log-file", default="execution.log",
        help="Path to the log file (default: execution.log)"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable DEBUG-level logging to console"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # ── run sub-command ───────────────────────────────────────────────────────
    run_parser = subparsers.add_parser(
        "run", help="Parse all state files and produce the master output dataset"
    )
    run_parser.add_argument(
        "--state", action="append", metavar="STATE_NAME",
        help="Limit processing to a specific state (repeatable). "
             "Example: --state Delaware --state Kansas"
    )
    run_parser.add_argument(
        "--format", action="append", choices=["csv", "json"],
        help="Output format(s) to produce (repeatable, default: csv and json)"
    )

    # ── verify sub-command ────────────────────────────────────────────────────
    verify_parser = subparsers.add_parser(
        "verify", help="Query the master dataset to verify a licensee"
    )
    verify_parser.add_argument(
        "--license-number", "-l",
        help="License number (partial match, case-insensitive)"
    )
    verify_parser.add_argument(
        "--business-name", "-b",
        help="Business name or DBA (partial match, case-insensitive)"
    )
    verify_parser.add_argument(
        "--state", action="append", metavar="STATE_NAME",
        help="Filter results to specific state(s)"
    )
    verify_parser.add_argument(
        "--status", choices=["Active", "Expired", "Unknown"],
        help="Filter by license status"
    )
    verify_parser.add_argument(
        "--export", metavar="FILE_PATH",
        help="Export matching results to a CSV or JSON file"
    )

    return parser


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    arg_parser = build_arg_parser()
    args = arg_parser.parse_args()

    setup_logging(log_file=args.log_file, verbose=args.verbose)

    if args.command == "run":
        cmd_run(args)
    elif args.command == "verify":
        cmd_verify(args)
    else:
        arg_parser.print_help()


if __name__ == "__main__":
    main()
