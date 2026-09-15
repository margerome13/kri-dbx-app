"""User role configuration for the KRI Intake app.

Roles: ADMIN, MAKER, CHECKER. A user's email not listed under any role is
UNAUTHORIZED and sees no pages other than an access-denied message. An email may
appear in more than one list (e.g. an admin who is also a checker) -- get_user_role()
resolves that to the single highest-privilege role, in the order below.

Which pages each role can see lives in ROLE_PAGES, keyed by the same page keys used
in view_groups.py's PAGE_REGISTRY.
"""
from typing import Optional

ADMINS = [
    "mar.abana@paymaya.com",
    "revylen.asilo@paymaya.com",
]

MAKERS = [
    "gilbert.lavides@paymaya.com",
]

CHECKERS = [
    "mar.abana@paymaya.com",
]

# Page keys a role can see. Admin can view all sections; Maker only Monthly Intake;
# Checker Monthly Intake plus Manage existing KRIs (not Add a KRI, not Lookup Values).
ROLE_PAGES = {
    "ADMIN": {"monthly_intake", "dashboard", "catalog_add", "catalog_manage", "lookup_admin"},
    "MAKER": {"monthly_intake"},
    "CHECKER": {"monthly_intake", "catalog_manage"},
}


def get_user_role(user_email: Optional[str]) -> str:
    """ADMIN, MAKER, CHECKER, or UNAUTHORIZED. Checked in that priority order, so a
    user listed under multiple roles gets the highest-privilege one."""
    email = (user_email or "").lower().strip()
    if email in (a.lower() for a in ADMINS):
        return "ADMIN"
    if email in (m.lower() for m in MAKERS):
        return "MAKER"
    if email in (c.lower() for c in CHECKERS):
        return "CHECKER"
    return "UNAUTHORIZED"


def pages_for_role(role: str) -> set:
    return ROLE_PAGES.get(role, set())


def can_view(user_email: Optional[str], page_key: str) -> bool:
    return page_key in pages_for_role(get_user_role(user_email))
