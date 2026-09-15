"""Append a row to kri_audit_log for every write the app makes to kri_catalog or
kri_monthly_submissions. Delta tables have no triggers, so this is called explicitly
right after each insert/update/delete.
"""
import json
from typing import Optional

from utils.db import TBL_AUDIT, build_insert, new_id, now_utc, run_statement


def log_change(
    table_name: str,
    record_key: str,
    action: str,
    changed_by: str,
    before: Optional[dict] = None,
    after: Optional[dict] = None,
) -> None:
    row = {
        "audit_id": new_id(),
        "table_name": table_name,
        "record_key": str(record_key),
        "action": action,
        "changed_by": changed_by,
        "changed_at": now_utc(),
        "before_value": json.dumps(before, default=str) if before else None,
        "after_value": json.dumps(after, default=str) if after else None,
    }
    run_statement(build_insert(TBL_AUDIT, row))
