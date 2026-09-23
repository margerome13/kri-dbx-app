"""Department-scoped data access for MAKER and CHECKER roles."""
from typing import Optional

from config.user_roles import get_user_department, get_user_role
from utils.db import sql_literal


def is_global_viewer(user_email: Optional[str]) -> bool:
    return get_user_role(user_email) == "ADMIN"


def scoped_department(user_email: Optional[str]) -> Optional[str]:
    """None = all departments (ADMIN). Otherwise the user's assigned department."""
    if is_global_viewer(user_email):
        return None
    return get_user_department(user_email)


def require_scoped_department(user_email: Optional[str]) -> str:
    """Department string for MAKER/CHECKER; stops the page if missing."""
    import streamlit as st

    dept = scoped_department(user_email)
    if dept:
        return dept
    st.error(
        "Your account has no department assigned. Ask an RCO administrator to set "
        "your department in **Administration → User Role Manager**."
    )
    st.stop()


def assert_department_allowed(user_email: Optional[str], department: str) -> bool:
    if is_global_viewer(user_email):
        return True
    scoped = scoped_department(user_email)
    return bool(scoped and scoped == department)


def catalog_department_clause(user_email: Optional[str], alias: str = "c") -> str:
    dept = scoped_department(user_email)
    if not dept:
        return ""
    return f" AND {alias}.department = {sql_literal(dept)}"


def plain_department_clause(user_email: Optional[str], column: str = "department") -> str:
    dept = scoped_department(user_email)
    if not dept:
        return ""
    return f" AND {column} = {sql_literal(dept)}"
