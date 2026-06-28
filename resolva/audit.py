"""
Audit log — append-only CSV, written simultaneously with every KB entry
(whether auto-published or SME-approved).

Reuses the toolkit's CSV audit structure, with the columns Resolva's spec
requires. The CSV lives in the per-user data directory, separate from the
SQLite knowledge base, so the trail is a plain, portable, tamper-evident
file an auditor can open in Excel without touching the app.
"""

import csv
from datetime import datetime
from .config import audit_path

COLUMNS = [
    "Ticket Number",
    "Date",
    "Account Number",       # sanitized internal 6-digit
    "Description",
    "Resolution",
    "Time to Resolve",
    "Stakeholders Involved",
    "Validation Process",   # auto | manual
    "Additional Comments",
]


def write_audit(row: dict) -> None:
    path = audit_path()
    exists = path.exists()
    record = [
        row.get("ticket_number", ""),
        row.get("date") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        row.get("account_number", ""),
        row.get("description", ""),
        row.get("resolution", ""),
        row.get("time_to_resolve", ""),
        row.get("stakeholders", ""),
        row.get("validation_process", ""),
        row.get("comments", ""),
    ]
    try:
        with open(path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not exists:
                writer.writerow(COLUMNS)
            writer.writerow(record)
    except OSError as e:
        print(f"[audit] failed to write CSV: {e}")


def read_audit() -> list:
    """Return the audit log as a list of dict rows (newest first) for display."""
    path = audit_path()
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return list(reversed(rows))
