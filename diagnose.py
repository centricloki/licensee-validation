"""
Quick diagnostic: run each missing state in isolation with verbose output.
"""
import logging
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s",
                    stream=sys.stdout)

from licensee_validation.pipeline import Pipeline

p = Pipeline("states_config.json")

for state in ["District of Columbia", "Kansas", "North Dakota", "Rhode Island", "Wisconsin"]:
    print(f"\n{'='*60}")
    print(f"STATE: {state}")
    print('='*60)
    records = p._process_state(state, p.config["states"][state])
    print(f"  -> TOTAL RECORDS: {len(records)}")
    if records:
        r = records[0]
        print(f"  -> SAMPLE: {r}")
