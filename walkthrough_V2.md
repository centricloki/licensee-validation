# Tobacco License Validation System
## Complete Installation & Testing Guide
**Republic Brands Compliance Tool — v1.0.0**

---

## Project Structure

```
licensee-validation/
├── main.py                          ← CLI entry point
├── states_config.json               ← Config-driven state mappings (NO hardcoding)
├── requirements.txt
├── execution.log                    ← Auto-generated on every run
│
├── distributors/                    ← Input files (organized by state name)
│   ├── Delaware/
│   │   └── Delaware_Business_Licenses_20260626.xlsx
│   ├── District of Columbia/
│   │   └── Basic_Business_License.csv
│   ├── Kansas/
│   │   └── tb84ALL.csv
│   ├── Kentucky/
│   │   └── Licensees 6-4-26.pdf
│   ├── North Dakota/
│   │   ├── Licensees-TobaccoRetail-byCity.pdf
│   │   └── Licensees-TobaccoWholesale.pdf
│   ├── Pennsylvania/
│   │   └── Tobacco_Products_Tax_Licenses_*.xlsx
│   ├── Rhode Island/
│   │   ├── Unified License List - May 27, 2026.pdf
│   │   └── Uniform_CTE_ DEALERSList_05152026.pdf
│   ├── Washington/
│   │   └── CIG_TOB_VAPE_021026.xlsx
│   └── Wisconsin/
│       └── TobLicList.csv
│
├── output/                          ← Auto-created on first run
│   ├── master_tobacco_licenses.csv
│   └── master_tobacco_licenses.json
│
├── quarantine/                      ← Files that failed parsing (auto-created)
│
└── licensee_validation/             ← Python package
    ├── __init__.py
    ├── models.py                    ← Canonical LicenseeRecord dataclass
    ├── base_parser.py               ← Abstract base with column mapping
    ├── normalizer.py                ← Date/string cleaning utilities
    ├── rules_engine.py              ← Status computation (Active/Expired/Unknown)
    ├── pipeline.py                  ← Orchestrator (discovery → parse → output)
    └── parsers/
        ├── __init__.py
        ├── excel_csv_parser.py      ← Handles .xlsx and .csv files
        └── pdf_parser.py            ← Handles PDF (table mode + text mode)
```

---

## 1. Prerequisites

- **Python 3.9+** (tested on Python 3.14)
- **pip** package manager

---

## 2. Installation

```powershell
# Navigate to the project directory
cd c:\AppCodeStore\AI-Model-Code\licensee-validation

# Install all dependencies
pip install -r requirements.txt
```

**Packages installed:**
| Package | Purpose |
|---|---|
| `pandas` | Excel / CSV reading and DataFrame operations |
| `openpyxl` | Excel `.xlsx` engine for pandas |
| `pdfplumber` | PDF table and text extraction |
| `pypdf` | PDF metadata and page count support |
| `python-dateutil` | Flexible multi-format date parsing |

---

## 3. Running the Pipeline

### Run ALL states (produces both CSV and JSON output)
```powershell
python main.py run
```

### Run a specific state only
```powershell
python main.py run --state Delaware
python main.py run --state "North Dakota"
python main.py run --state Pennsylvania
```

### Run multiple specific states
```powershell
python main.py run --state Kansas --state Wisconsin --state "Rhode Island"
```

### Output format control
```powershell
# CSV only
python main.py run --format csv

# JSON only
python main.py run --format json

# Both (default)
python main.py run --format csv --format json
```

### Enable verbose/debug logging
```powershell
python main.py run --verbose
```

### Use a custom config file
```powershell
python main.py run --config my_states_config.json
```

### Custom log file location
```powershell
python main.py run --log-file logs/my_run.log
```

---

## 4. Verifying Licenses

After running the pipeline, use the `verify` command to query the master dataset.

### Verify by license number (partial match, case-insensitive)
```powershell
python main.py verify --license-number TD000567
python main.py verify --license-number "1000"
```

### Verify by business name (partial match, case-insensitive)
```powershell
python main.py verify --business-name "Core-Mark"
python main.py verify --business-name "7HILLS"
python main.py verify --business-name "TOBACCO"
```

### Filter by state
```powershell
python main.py verify --business-name "Core-Mark" --state Kentucky
python main.py verify --license-number "TD" --state Kansas
```

### Show only Active licenses
```powershell
python main.py verify --status Active
python main.py verify --status Expired
python main.py verify --status Unknown
```

### Combined search
```powershell
python main.py verify --business-name "LLC" --state Wisconsin --status Active
```

### Export verification results
```powershell
# Export to CSV
python main.py verify --business-name "Core-Mark" --export results.csv

# Export to JSON
python main.py verify --license-number TD000567 --export match.json
```

---

## 5. Canonical Output Schema

All parsed records are normalized into a single unified format:

| Field | Description | Example |
|---|---|---|
| `state` | Source state name | `Kansas` |
| `license_number` | License/permit number | `TD000567` |
| `legal_name` | Registered legal name | `7HILLS KANSAS CITY LLC` |
| `dba` | Doing Business As | `7HILLS` |
| `address` | Street address | `4233 RAINBOW BLVD` |
| `city` | City | `KANSAS CITY` |
| `state_code` | 2-letter state code | `KS` |
| `zip` | 5-digit zip | `66103` |
| `issue_date` | License issue date (`YYYY-MM-DD`) | `2026-01-01` |
| `expiration_date` | License expiry date (`YYYY-MM-DD`) | `2026-12-31` |
| `status` | Computed status | `Active` / `Expired` / `Unknown` |
| `license_type` | License classification | `Tobacco Distributor` |
| `source_file_name` | Source file name | `tb84ALL.csv` |
| `parsed_at` | UTC timestamp of parsing | `2026-06-29T13:30:00Z` |

---

## 6. Status Computation Rules

| Rule | States | Logic |
|---|---|---|
| `date_based` | DE, DC, PA, WA, WI, ND | `Active` if `expiration_date >= today`, else `Expired` |
| `year_end_expiry` | Kansas | `expiration_date = Dec 31` of the issue year |
| `header_period` | Kentucky, Rhode Island | `expiration_date = Jun 30` of the period year from PDF header |

---

## 7. Logging

Logs are written to both **console** and **`execution.log`** simultaneously.

| Level | Meaning |
|---|---|
| `INFO` | Successful steps (file opened, rows processed, output written) |
| `WARNING` | Row-level issues (empty license number, unparseable date, unmatched PDF line) |
| `ERROR` | File-level failures (corrupt file, wrong format) — file moved to `/quarantine/` |

**Sample log output:**
```
2026-06-29 13:30:51 | INFO     | pipeline | Discovered 1 file(s) in distributors\Kansas
2026-06-29 13:30:51 | INFO     | excel_csv_parser | [Kansas] Processing 158 rows from tb84ALL.csv
2026-06-29 13:30:51 | INFO     | excel_csv_parser | [Kansas] Parsed 158 valid records from tb84ALL.csv
2026-06-29 13:30:51 | INFO     | pipeline | [Kansas] [OK] tb84ALL.csv -> 158 records
```

---

## 8. Adding a New State

1. **Place the file** in `distributors/<State Name>/` folder.
2. **Add a config block** in `states_config.json` under `"states"`:

```json
"New State": {
  "file_type": "csv",
  "file_pattern": "*.csv",
  "filter": null,
  "column_map": {
    "RAW_COL_LICENSE": "license_number",
    "RAW_COL_NAME": "legal_name",
    "RAW_COL_EXPIRY": "expiration_date"
  },
  "status_rule": "date_based",
  "expiration_date_field": "expiration_date"
}
```

3. **Run** `python main.py run --state "New State"` — no code changes needed.

---

## 9. Quick Test Checklist

```powershell
# 1. Run full pipeline
python main.py run

# 2. Verify output files exist
dir output\

# 3. Check record counts in summary printed to console

# 4. Test license lookup
python main.py verify --license-number TD000567

# 5. Test name search
python main.py verify --business-name "Core-Mark"

# 6. Test status filter
python main.py verify --status Expired --state Washington

# 7. Test export
python main.py verify --status Active --state Kansas --export kansas_active.csv

# 8. Check log file
type execution.log | more
```

---

> [!IMPORTANT]
> When adding new state files, the folder name under `distributors/` must **exactly match** the state key in `states_config.json` (case-sensitive).

> [!TIP]
> To re-process a single state after updating its source file, use `python main.py run --state "State Name"`. It overwrites the output files with the latest data.

> [!NOTE]
> Files that fail to parse (corrupted, wrong format) are automatically copied to the `/quarantine/<state>/` directory for review, and the pipeline continues with other states.
