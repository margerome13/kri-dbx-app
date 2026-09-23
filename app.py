import streamlit as st

from config.user_roles import get_user_department, get_user_role
from utils.db import current_user_email
from view_groups import get_groups_for_user

st.set_page_config(
    page_title="Maya KRI — Risk & Compliance Office",
    page_icon=":material/monitoring:",
    layout="wide",
)
st.logo("assets/maya_logo.png")
st.title(":material/monitoring: Maya KRI — Risk & Compliance Office")

user_email = current_user_email()
role = get_user_role(user_email)
dept = get_user_department(user_email)

if role in ("MAKER", "CHECKER"):
    if dept:
        dept_part = f" · **Department:** {dept}"
    else:
        dept_part = " · **Department:** *(not set — ask an Admin)*"
else:
    dept_part = ""

role_icons = {
    "ADMIN": ("🔑", "success"),
    "MAKER": ("📝", "info"),
    "CHECKER": ("✅", "warning"),
}
icon, tone = role_icons.get(role, ("🚫", "error"))
identity_line = (
    f"{icon} **Role:** {role}{dept_part} &nbsp;&nbsp;|&nbsp;&nbsp; "
    f"👤 **Logged in as:** {user_email}"
)
getattr(st, tone)(identity_line)

pages = {
    group["title"]: [
        st.Page(view["page"], title=view["label"], icon=view["icon"])
        for view in group["views"]
    ]
    for group in get_groups_for_user(user_email)
}

pg = st.navigation(pages)
pg.run()
