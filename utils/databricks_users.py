"""Databricks workspace user directory for User Role Manager email validation."""
from __future__ import annotations

import streamlit as st

from utils.db import run_query

# Direct members of the app's Databricks group(s) — used to constrain User Role Manager.
DATABRICKS_GROUP_USERS_VIEW = "dba_prod.data_eng.databricks_group_users_view"


@st.cache_data(ttl=300, show_spinner=False)
def fetch_direct_group_user_emails() -> tuple[list[str], str | None]:
    """Return (sorted emails, error_message). error_message is set when the query fails."""
    try:
        df = run_query(
            f"""
            SELECT DISTINCT TRIM(`user`) AS user_email
            FROM {DATABRICKS_GROUP_USERS_VIEW}
            WHERE is_direct_group = true
              AND `user` IS NOT NULL
              AND TRIM(`user`) != ''
              AND TRIM(`user`) LIKE '%@%'
            ORDER BY user_email
            """
        )
    except Exception as exc:
        return [], (
            f"Could not load Databricks group users from `{DATABRICKS_GROUP_USERS_VIEW}` "
            f"({exc}). Grant the app SELECT on this view."
        )
    if df.empty:
        return [], (
            f"No direct group users returned from `{DATABRICKS_GROUP_USERS_VIEW}`. "
            "Check `is_direct_group = true` rows or view permissions."
        )
    emails = [str(e).strip() for e in df["user_email"].tolist() if str(e).strip()]
    return sorted(set(emails), key=str.lower), None


def allowed_email_set(emails: list[str]) -> frozenset[str]:
    return frozenset(e.lower() for e in emails)


def validate_databricks_group_email(
    email: str,
    allowed: frozenset[str],
    *,
    existing_role_emails: frozenset[str] | None = None,
) -> str | None:
    if not email or not email.strip():
        return "User email is required."
    key = email.strip().lower()
    if key in allowed:
        return None
    if existing_role_emails and key in existing_role_emails:
        return None
    return (
        "User email must be a direct Databricks group member "
        f"(`{DATABRICKS_GROUP_USERS_VIEW}`, `is_direct_group = true`)."
    )
