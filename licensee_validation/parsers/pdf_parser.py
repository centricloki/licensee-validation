# licensee_validation/parsers/pdf_parser.py
"""
Generic PDF parser for tobacco license files.

Handles two distinct PDF structures (driven by states_config.json -> pdf_mode):

  pdf_mode = "table"
    -> pdfplumber extracts tables page-by-page.
    -> Used by: Kentucky

  pdf_mode = "text"
    -> pdfplumber extracts raw page text, then we parse fixed-width-like rows.
    -> Used by: North Dakota, Rhode Island

For header_period rules (KY, RI), the period year is extracted from page-1
header text and passed to the rules engine.
"""

import logging
import os
import re
from typing import List, Optional

import pdfplumber

from ..base_parser import BaseParser
from ..models import LicenseeRecord
from ..normalizer import clean_str, extract_period_year_from_header

logger = logging.getLogger(__name__)

# ── Module-level regex constants ──────────────────────────────────────────────

# ND-style license codes at LINE start (e.g. TR9777, TW0335).
# re.MULTILINE flag ensures ^ matches each line, not just string start.
_LICENSE_PREFIX_RE = re.compile(r"(?m)^[A-Z]{2}\d{4,}")

# US state abbreviation + 5-digit zip at end of line (for RI records)
_RI_STATE_ZIP_RE = re.compile(
    r"^(.*?)\s+([A-Z]{2})\s+(\d{5}(?:-\d{4})?)\s*$"
)

# Street number anchor pattern: digits followed by an uppercase letter word
_STREET_NUM_RE = re.compile(r"\b(\d{1,5})\s+[A-Z]")

# Street-type suffixes used to split address from city in RI/ND records
_STREET_SUFFIXES = {
    "ST", "AVE", "RD", "DR", "LN", "BLVD", "WAY", "CT", "PL", "HWY",
    "STE", "APT", "FL", "PKWY", "CIR", "TRL", "EXPY", "FWY", "MAIN",
    "LOOP", "RTE", "RT", "BOX", "PO", "SQ", "PIKE", "PATH", "PASS",
}


class PdfParser(BaseParser):
    """Parses PDF tobacco license files (table or text mode)."""

    # ND full-line regex (single-spaced pdfplumber output):
    # TR9777 001 LLC FORT SALOON 505 BROADWAY ABERCROMBIE RICHLAND ND 58001 (701) 388-3549 6/30/2026 Issued
    _ND_FULL_RE = re.compile(
        r"^(?P<license>[A-Z]{2}\d{4,})\s+"
        r"(?P<middle>.+?)\s+"
        r"(?P<state>[A-Z]{2})\s+"
        r"(?P<zip>\d{5}(?:-\d{4})?)\s+"
        r"(?P<phone>\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4})\s+"
        r"(?P<expiry>\d{1,2}/\d{1,2}/\d{4})\s+"
        r"(?P<license_status>\w+)\s*$"
    )

    # ── Public API ────────────────────────────────────────────────────────────

    def parse(self, file_path: str) -> List[LicenseeRecord]:
        records: List[LicenseeRecord] = []
        source_name = os.path.basename(file_path)
        pdf_mode = self.state_cfg.get("pdf_mode", "table")

        logger.info("[%s] Reading PDF (%s mode): %s", self.state_name, pdf_mode, file_path)

        try:
            with pdfplumber.open(file_path) as pdf:
                period_year = self._extract_period_year(pdf)
                if pdf_mode == "table":
                    records = self._parse_table_mode(pdf, source_name, period_year)
                else:
                    records = self._parse_text_mode(pdf, source_name, period_year)
        except Exception as exc:
            logger.error("[%s] Failed to open PDF %r: %s", self.state_name, file_path, exc)
            raise  # pipeline will quarantine

        logger.info("[%s] Parsed %d valid records from %s",
                    self.state_name, len(records), source_name)
        return records

    # ── Period-year extraction ────────────────────────────────────────────────

    def _extract_period_year(self, pdf) -> Optional[int]:
        """
        Scan page-1 text for an end-year in a license period statement.
        Only relevant for header_period status rules (KY, RI).
        """
        if self.state_cfg.get("status_rule") != "header_period":
            return None
        try:
            text = pdf.pages[0].extract_text() or ""
            year = extract_period_year_from_header(text)
            if year:
                logger.info("[%s] Detected period year %d from header",
                            self.state_name, year)
            return year
        except Exception as exc:
            logger.warning("[%s] Could not extract period year: %s", self.state_name, exc)
            return None

    # =========================================================================
    # TABLE MODE  (Kentucky)
    # =========================================================================

    def _parse_table_mode(self, pdf, source_name: str,
                          period_year: Optional[int]) -> List[LicenseeRecord]:
        """
        Extract tables page-by-page.  The first row whose cells contain
        header_row_keywords becomes the column header; all later rows are data.
        Rows containing skip_rows_containing fragments are ignored.
        """
        records: List[LicenseeRecord] = []
        header_keywords = [kw.lower()
                           for kw in self.state_cfg.get("header_row_keywords", [])]
        skip_fragments  = [s.lower()
                           for s in self.state_cfg.get("skip_rows_containing", [])]

        headers: Optional[List[str]] = None
        rows_seen = 0

        for page_num, page in enumerate(pdf.pages, start=1):
            try:
                tables = page.extract_tables()
            except Exception as exc:
                logger.warning("[%s] Page %d table extract failed: %s",
                               self.state_name, page_num, exc)
                continue

            for table in tables:
                for row in table:
                    if row is None:
                        continue
                    cells       = [clean_str(c) for c in row]
                    lower_cells = [c.lower() for c in cells]

                    # --- locate header row ---
                    if headers is None:
                        if any(kw in lower_cells for kw in header_keywords):
                            headers = cells
                            logger.info("[%s] Header found on page %d: %s",
                                        self.state_name, page_num, headers)
                        continue

                    if not any(cells):
                        continue

                    row_text = " ".join(cells).lower()
                    if any(skip in row_text for skip in skip_fragments):
                        continue

                    raw = dict(zip(headers, cells))
                    rows_seen += 1

                    try:
                        record = self._map_row(raw, source_name, period_year=period_year)
                        if record:
                            records.append(record)
                    except Exception as exc:
                        logger.warning("[%s] Row skipped (table mode): %s | row=%s",
                                       self.state_name, exc, cells[:4])

        logger.info("[%s] Table mode: %d raw rows, %d records",
                    self.state_name, rows_seen, len(records))
        return records

    # =========================================================================
    # TEXT MODE  (North Dakota, Rhode Island)
    # =========================================================================

    def _parse_text_mode(self, pdf, source_name: str,
                         period_year: Optional[int]) -> List[LicenseeRecord]:
        """
        Dispatch to ND or RI parser based on whether ND-style license codes
        (TR/TW + 4+ digits) appear at line-starts in the extracted text.
        """
        pages_text: List[str] = []
        for page in pdf.pages:
            try:
                pages_text.append(page.extract_text() or "")
            except Exception:
                pages_text.append("")

        full_text = "\n".join(pages_text)

        if _LICENSE_PREFIX_RE.search(full_text):
            logger.info("[%s] Detected ND-style license codes - using ND parser",
                        self.state_name)
            return self._parse_nd_style(pages_text, source_name, period_year)
        else:
            logger.info("[%s] No license-code prefixes found - using RI parser",
                        self.state_name)
            return self._parse_ri_style(pdf, pages_text, source_name, period_year)

    # =========================================================================
    # NORTH DAKOTA PARSER
    # =========================================================================

    def _parse_nd_style(self, pages_text: List[str], source_name: str,
                        period_year: Optional[int]) -> List[LicenseeRecord]:
        """
        ND PDF (pdfplumber single-spaced output) example:
          TR9777 001 LLC FORT SALOON 505 BROADWAY ABERCROMBIE RICHLAND ND 58001 (701) 388-3549 6/30/2026 Issued

        Strategy:
          1. Accumulate lines until the NEXT license-code line is seen.
          2. Flush the accumulated record using _ND_FULL_RE to extract:
             license, middle (name+addr+city+county), state, zip, phone, expiry, status.
          3. Use street-number anchor to split middle into name / address / city / county.
        """
        records: List[LicenseeRecord] = []

        meta_markers = [
            "Report Parameters", "License Status:", "New or Renew:",
            "Expiration Date:", "License Type:", "County:", "Sort Order:",
            "North Dakota Attorney General", "License List",
            "Licensee Legal Name", "License Date", "Number",
        ]

        current_line: Optional[str] = None

        def flush(line: Optional[str]) -> None:
            if not line:
                return
            m = self._ND_FULL_RE.match(line.strip())
            if not m:
                logger.warning("[%s] ND line did not match full regex: %r",
                               self.state_name, line[:100])
                return

            license_num = m.group("license")
            middle      = m.group("middle").strip()
            state_code  = m.group("state")
            zip_code    = m.group("zip")
            expiry      = m.group("expiry")
            lic_status  = m.group("license_status")

            # Split middle: find street-number anchor
            street_m = _STREET_NUM_RE.search(middle)
            if street_m:
                name_dba    = middle[: street_m.start()].strip()
                addr_onward = middle[street_m.start():].strip()
                parts       = addr_onward.split()
                if len(parts) >= 3:
                    county  = parts[-1]
                    city    = parts[-2]
                    address = " ".join(parts[:-2])
                elif len(parts) == 2:
                    county  = ""
                    city    = parts[-1]
                    address = parts[0]
                else:
                    county  = ""
                    city    = ""
                    address = addr_onward
            else:
                name_dba = middle
                address = city = county = ""

            raw = {
                "License":             license_num,
                "Licensee Legal Name": name_dba,
                "DBA":                 "",
                "Business Address":    address,
                "City":                city,
                "County":              county,
                "State":               state_code,
                "Zip":                 zip_code,
                "Phone":               m.group("phone"),
                "Expiration Date":     expiry,
                "License Status":      lic_status,
            }

            try:
                record = self._map_row(raw, source_name, period_year=period_year)
                if record:
                    records.append(record)
            except Exception as exc:
                logger.warning("[%s] ND row skipped: %s | raw=%s",
                               self.state_name, exc, list(raw.values())[:5])

        for page_text in pages_text:
            for line in page_text.splitlines():
                line = line.strip()
                if not line:
                    continue
                if any(meta in line for meta in meta_markers):
                    continue
                first_token = line.split()[0] if line.split() else ""
                if re.match(r"^[A-Z]{2}\d{4,}", first_token):
                    flush(current_line)
                    current_line = line
                # else: skip continuation / mailing-address lines

        flush(current_line)  # flush last record

        logger.info("[%s] ND text mode: extracted %d records",
                    self.state_name, len(records))
        return records

    # =========================================================================
    # RHODE ISLAND PARSER
    # =========================================================================

    def _parse_ri_style(self, pdf, pages_text: List[str], source_name: str,
                        period_year: Optional[int]) -> List[LicenseeRecord]:
        """
        RI PDF: each record is a flat single-space line like:
          "HOPKINTON LIQUOR DEPOT 229 MAIN ST ASHAWAY RI 02804"

        Strategy:
          1. Collect all candidate lines from extract_text() AND extract_tables() cells.
          2. Deduplicate.
          3. Parse each line with _parse_ri_record_line().
          4. Generate a surrogate license number (RI-XXXXX-NNNN) since RI provides none.
        """
        records: List[LicenseeRecord] = []
        row_idx = 0

        skip_patterns = [
            "Rhode Island", "07/01/", "06/30/", "Updated", "In accordance",
            "licensed distributor", "licensed importer", "manufacturer", "importer",
            "Name Addre", "Name Address", "City State Zip", "Gen. Laws",
            "licensed dealers", "ENDS products", "Division of Taxation",
            "distributor of ENDS", "Only those",
        ]

        candidate_lines: List[str] = []

        # Source 1: page text lines
        for page_text in pages_text:
            for line in page_text.splitlines():
                candidate_lines.append(line.strip())

        # Source 2: table cell content (captures single-cell table PDFs)
        for page in pdf.pages:
            try:
                for table in (page.extract_tables() or []):
                    for row in table:
                        if row:
                            for cell in row:
                                if cell:
                                    cell_text = clean_str(cell)
                                    if cell_text:
                                        candidate_lines.append(cell_text)
            except Exception:
                pass

        seen: set = set()
        for line in candidate_lines:
            if not line or len(line) < 10:
                continue
            if any(skip.lower() in line.lower() for skip in skip_patterns):
                continue
            if line in seen:
                continue
            seen.add(line)

            parsed = self._parse_ri_record_line(line)
            if not parsed:
                continue

            row_idx += 1
            file_tag = source_name[:6].upper().replace(" ", "").replace("_", "")
            parsed["License Number"] = f"RI-{file_tag}-{row_idx:04d}"

            col_map_backup = self.column_map.copy()
            self.column_map["License Number"] = "license_number"

            try:
                record = self._map_row(parsed, source_name, period_year=period_year)
                if record:
                    records.append(record)
            except Exception as exc:
                logger.warning("[%s] RI row skipped: %s | parsed=%s",
                               self.state_name, exc, parsed)
            finally:
                self.column_map = col_map_backup

        logger.info("[%s] RI text mode: extracted %d records",
                    self.state_name, len(records))
        return records

    def _parse_ri_record_line(self, text: str) -> Optional[dict]:
        """
        Parse a flat RI address line like:
          "HOPKINTON LIQUOR DEPOT 229 MAIN ST ASHAWAY RI 02804"

        Returns: dict with Name, Address, City, State, Zip — or None if invalid.
        """
        m = _RI_STATE_ZIP_RE.match(text.strip())
        if not m:
            return None

        remainder  = m.group(1).strip()
        state_code = m.group(2)
        zip_code   = m.group(3)

        if not state_code.isalpha():
            return None

        street_m = _STREET_NUM_RE.search(remainder)
        if street_m:
            name          = remainder[: street_m.start()].strip()
            addr_and_city = remainder[street_m.start():].strip()
            parts         = addr_and_city.split()

            # Find last street-type suffix to delimit address vs city
            split_idx: Optional[int] = None
            for i, part in enumerate(parts):
                if part.upper().rstrip(".") in _STREET_SUFFIXES:
                    split_idx = i

            if split_idx is not None and split_idx < len(parts) - 1:
                address = " ".join(parts[: split_idx + 1])
                city    = " ".join(parts[split_idx + 1:])
            else:
                address = " ".join(parts[:-1]) if len(parts) > 1 else addr_and_city
                city    = parts[-1] if len(parts) > 1 else ""
        else:
            name    = remainder
            address = ""
            city    = ""

        if not name or len(name) < 3:
            return None

        return {
            "Name":    name,
            "Address": address,
            "City":    city,
            "State":   state_code,
            "Zip":     zip_code,
        }
