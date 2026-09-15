"""Server-side page guard.

view_groups.py already only lists pages a role is allowed to see, so an
unauthorized page normally never appears in the sidebar at all. This is a second,
cheap check inside the page itself -- defense in depth against someone bookmarking
or otherwise navigating directly to a page slug their role shouldn't reach.
"""
import streamlit as st

from config.user_roles import can_view
from utils.db import current_user_email


def require_page_access(page_key: str) -> None:
    email = current_user_email()
    if not can_view(email, page_key):
        st.error(
            "You don't have access to this page. Contact your Risk & Compliance "
            "Office administrator if you believe this is a mistake."
        )
        st.stop()
