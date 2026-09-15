import streamlit as st

from view_groups import groups

st.set_page_config(
    page_title="KRI Intake — Risk & Compliance Office",
    page_icon=":material/monitoring:",
    layout="wide",
)
st.title(":material/monitoring: KRI Intake — Risk & Compliance Office")

pages = {
    group["title"]: [
        st.Page(view["page"], title=view["label"], icon=view["icon"])
        for view in group["views"]
    ]
    for group in groups
}

pg = st.navigation(pages)
pg.run()
