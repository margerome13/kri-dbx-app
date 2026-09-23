"""User role configuration for the Maya KRI app.

Roles are ADMIN, MAKER, or CHECKER, and normally live in the
dg_dev.sandbox.kri_user_roles table -- managed in-app via Administration ->
User Role Manager, no code change or redeploy needed.

BOOTSTRAP_ADMINS is the one exception: a small hardcoded list that is always
ADMIN regardless of what's in that table. It exists so the roles table can never
be emptied, corrupted, or misconfigured into locking every admin out -- there is
always at least one way back in. Keep this list as short as possible.
"""
from typing import Optional

import pandas as pd

BOOTSTRAP_ADMINS = [
    "mar.abana@paymaya.com",
]

VALID_ROLES = ("ADMIN", "MAKER", "CHECKER")

ROLE_PAGES = {
    "ADMIN": {
        "monthly_intake",
        "review_submissions",
        "dashboard",
        "catalog_add",
        "catalog_manage",
        "lookup_admin",
        "user_role_admin",
    },
    "MAKER": {"monthly_intake"},
    "CHECKER": {"review_submissions"},
}


def _load_role_rows() -> dict[str, dict]:
    """{lowercased user_email: {role, department}} from kri_user_roles."""
    from utils.db import TBL_USER_ROLES, run_query

    try:
        df = run_query(
            f"SELECT user_email, role, department FROM {TBL_USER_ROLES}"
        )
    except Exception:
        try:
            df = run_query(f"SELECT user_email, role FROM {TBL_USER_ROLES}")
            df["department"] = None
        except Exception:
            return {}
    if df.empty:
        return {}
    rows = {}
    for _, r in df.iterrows():
        email = str(r["user_email"]).lower()
        dept = r.get("department")
        if dept is None or (isinstance(dept, float) and pd.isna(dept)):
            dept_val = None
        else:
            dept_val = str(dept).strip() or None
        rows[email] = {"role": r["role"], "department": dept_val}
    return rows


def _load_role_table() -> dict[str, str]:
    return {email: row["role"] for email, row in _load_role_rows().items()}


def _resolve_role(user_email: Optional[str], role_table: dict) -> str:
    """Pure resolution logic, separated from _load_role_table() so it can be unit
    tested with a hand-built role_table and no database dependency."""
    email = (user_email or "").lower().strip()
    if email in (a.lower() for a in BOOTSTRAP_ADMINS):
        return "ADMIN"
    role = role_table.get(email)
    return role if role in VALID_ROLES else "UNAUTHORIZED"


def get_user_role(user_email: Optional[str]) -> str:
    return _resolve_role(user_email, _load_role_table())


def get_user_department(user_email: Optional[str]) -> Optional[str]:
    if get_user_role(user_email) == "ADMIN":
        return None
    email = (user_email or "").lower().strip()
    row = _load_role_rows().get(email)
    if not row:
        return None
    return row.get("department")


def pages_for_role(role: str) -> set:
    return ROLE_PAGES.get(role, set())


def can_view(user_email: Optional[str], page_key: str) -> bool:
    return page_key in pages_for_role(get_user_role(user_email))
