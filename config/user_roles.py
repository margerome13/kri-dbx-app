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

BOOTSTRAP_ADMINS = [
    "mar.abana@paymaya.com",
]

VALID_ROLES = ("ADMIN", "MAKER", "CHECKER")

# Page keys a role can see. Admin can view all sections; Maker only Monthly
# Intake; Checker Monthly Intake plus Manage Existing KRIs (not Add a KRI, not
# Lookup Values, not User Role Manager).
ROLE_PAGES = {
    "ADMIN": {
        "monthly_intake",
        "dashboard",
        "catalog_add",
        "catalog_manage",
        "lookup_admin",
        "user_role_admin",
    },
    "MAKER": {"monthly_intake"},
    "CHECKER": {"monthly_intake", "catalog_manage"},
}


def _load_role_table() -> dict:
    """{lowercased user_email: role}, freshly queried from kri_user_roles on every
    call -- this app doesn't cache any data query, so role lookups aren't an
    exception. Returns {} rather than raising if the query fails, so a table or
    connection problem can't lock everyone out; BOOTSTRAP_ADMINS resolves
    independently of this.
    """
    from utils.db import TBL_USER_ROLES, run_query

    try:
        df = run_query(f"SELECT user_email, role FROM {TBL_USER_ROLES}")
    except Exception:
        return {}
    if df.empty:
        return {}
    return {str(email).lower(): role for email, role in zip(df["user_email"], df["role"])}


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


def pages_for_role(role: str) -> set:
    return ROLE_PAGES.get(role, set())


def can_view(user_email: Optional[str], page_key: str) -> bool:
    return page_key in pages_for_role(get_user_role(user_email))
