# Task: Tobacco License Validation System

## Phase 1 — Project Skeleton
- [x] Create project directory structure
- [x] Create `requirements.txt`
- [x] Create `states_config.json` (config-driven state mappings)

## Phase 2 — Core Library
- [x] `licensee_validation/models.py` — Canonical dataclass
- [x] `licensee_validation/base_parser.py` — Abstract base parser
- [x] `licensee_validation/normalizer.py` — Date/field normalization
- [x] `licensee_validation/rules_engine.py` — Status computation

## Phase 3 — State Parsers
- [x] `licensee_validation/parsers/excel_csv_parser.py` — Generic Excel/CSV parser (DE, DC, PA, WA, WI, KS)
- [x] `licensee_validation/parsers/pdf_parser.py` — Generic PDF parser (KY, ND, RI)

## Phase 4 — Pipeline Orchestration
- [x] `licensee_validation/pipeline.py` — Orchestrates all states
- [x] `main.py` — CLI entry point (--state, --output, --format, --verify)

## Phase 5 — Testing & Verification
- [ ] Run full pipeline and validate output CSV/JSON
- [ ] Test `--verify` command for license lookup
- [ ] Verify log output (console + file)
