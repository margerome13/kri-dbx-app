import streamlit as st

from utils.db import current_user_email

st.header("Access Denied", divider=True)
st.error(
    f"**{current_user_email()}** is not yet authorized to use this app. Please "
    "contact your Risk & Compliance Office administrator to request access."
)
