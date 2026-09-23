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

badge_col, id_col = st.columns([1, 3])
with badge_col:
    if role == "ADMIN":
        st.success(f"🔑 Role: {role}")
    elif role == "MAKER":
        st.info(f"📝 Role: {role}")
    elif role == "CHECKER":
        st.warning(f"✅ Role: {role}")
    else:
        st.error(f"🚫 Role: {role}")
with id_col:
    dept = get_user_department(user_email)
    dept_line = f" · **Department:** {dept}" if dept and role in ("MAKER", "CHECKER") else ""
    st.caption(f"👤 Logged in as **{user_email}**{dept_line}")

pages = {
    group["title"]: [
        st.Page(view["page"], title=view["label"], icon=view["icon"])
        for view in group["views"]
    ]
    for group in get_groups_for_user(user_email)
}

pg = st.navigation(pages)
pg.run()
