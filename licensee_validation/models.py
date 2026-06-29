# licensee_validation/models.py
"""
Canonical data model for a normalized tobacco licensee record.
All state parsers output a list of LicenseeRecord instances.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class LicenseeRecord:
    """
    Unified representation of a single tobacco licensee record,
    regardless of source state or file format.
    """
    state: str = ""
    license_number: str = ""
    legal_name: str = ""
    dba: str = ""
    address: str = ""
    city: str = ""
    state_code: str = ""
    zip: str = ""
    issue_date: Optional[str] = None          # YYYY-MM-DD or None
    expiration_date: Optional[str] = None     # YYYY-MM-DD or None
    status: str = "Unknown"                   # Active | Expired | Unknown
    license_type: str = ""
    source_file_name: str = ""
    parsed_at: str = ""

    def to_dict(self) -> dict:
        """Return record as a plain dictionary."""
        return asdict(self)

    def __repr__(self) -> str:
        return (
            f"LicenseeRecord(state={self.state!r}, license_number={self.license_number!r}, "
            f"legal_name={self.legal_name!r}, status={self.status!r}, "
            f"expiration_date={self.expiration_date!r})"
        )
