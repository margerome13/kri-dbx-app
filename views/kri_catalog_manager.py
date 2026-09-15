from datetime import date

import streamlit as st

from utils.audit import log_change
from utils.db import (
    TBL_CATALOG,
    build_insert,
    build_update,
    current_user_email,
    fetch_lookup,
    now_utc,
    run_query,
    run_statement,
    sql_literal,
)

st.header("KRI Catalog Manager", divider=True)
st.write(
    "Define the KRIs each department reports on: title, description, thresholds, and "
    "monitoring frequency. This is the reference catalog the monthly intake form reads from."
)

tab_add, tab_manage = st.tabs(["Add a KRI", "Manage existing KRIs"])

entities = fetch_lookup("entity")
departments = fetch_lookup("department")
risk_categories = fetch_lookup("risk_category")
frequencies = fetch_lookup("frequency")
units = fetch_lookup("unit_of_measure")
statuses = fetch_lookup("kri_status")

with tab_add:
    with st.form("add_kri_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            entity = st.selectbox("Entity", entities)
        with col2:
            department = st.selectbox("Department", departments)
        with col3:
            risk_category = st.selectbox("Risk category", risk_categories)

        kri_title = st.text_input("KRI title")
        description = st.text_area("Description / calculation formula", height=100)

        col4, col5 = st.columns(2)
        with col4:
            frequency = st.selectbox("Frequency", frequencies)
        with col5:
            unit_of_measure = st.selectbox("Unit of measure", units)

        data_source = st.text_input("Data source / point of contact")

        col6, col7, col8 = st.columns(3)
        with col6:
            threshold_green = st.text_input("Green threshold")
        with col7:
            threshold_amber = st.text_input("Amber threshold")
        with col8:
            threshold_red = st.text_input("Red threshold")

        date_approved = st.date_input("Date approved", value=date.today())

        submitted = st.form_submit_button("Add KRI", type="primary")
        if submitted:
            if not kri_title.strip():
                st.error("KRI title is required.")
            else:
                user = current_user_email()
                row = {
                    "entity": entity,
                    "department": department,
                    "risk_category": risk_category,
                    "kri_title": kri_title.strip(),
                    "description": description.strip() or None,
                    "unit_of_measure": unit_of_measure,
                    "frequency": frequency,
                    "data_source": data_source.strip() or None,
                    "threshold_green": threshold_green.strip() or None,
                    "threshold_amber": threshold_amber.strip() or None,
                    "threshold_red": threshold_red.strip() or None,
                    "kri_status": "Active",
                    "date_approved": date_approved,
                    "created_by": user,
                    "created_at": now_utc(),
                }
                run_statement(build_insert(TBL_CATALOG, row))

                new_row = run_query(
                    f"SELECT kri_id FROM {TBL_CATALOG} WHERE entity = {sql_literal(entity)} "
                    f"AND department = {sql_literal(department)} "
                    f"AND kri_title = {sql_literal(kri_title.strip())} "
                    f"ORDER BY kri_id DESC LIMIT 1"
                )
                kri_id = int(new_row.iloc[0]["kri_id"]) if not new_row.empty else None
                log_change(
                    table_name="kri_catalog",
                    record_key=kri_id,
                    action="INSERT",
                    changed_by=user,
                    after=row,
                )
                st.success(f"KRI '{kri_title}' added.")
                st.cache_data.clear()

with tab_manage:
    filter_entity = st.selectbox("Filter by entity", ["All"] + entities, key="manage_filter_entity")
    where = "" if filter_entity == "All" else f"WHERE entity = {sql_literal(filter_entity)}"
    catalog_df = run_query(
        f"SELECT kri_id, entity, department, risk_category, kri_title, frequency, "
        f"unit_of_measure, threshold_green, threshold_amber, threshold_red, kri_status "
        f"FROM {TBL_CATALOG} {where} ORDER BY entity, department, kri_title"
    )

    if catalog_df.empty:
        st.info("No KRIs found.")
    else:
        st.dataframe(catalog_df, use_container_width=True, hide_index=True)

        selected_id = st.selectbox(
            "Select a KRI to edit its status/thresholds",
            catalog_df["kri_id"].tolist(),
            format_func=lambda kid: catalog_df.loc[catalog_df["kri_id"] == kid, "kri_title"].iloc[0],
        )
        row = catalog_df[catalog_df["kri_id"] == selected_id].iloc[0]

        with st.form("edit_kri_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                new_green = st.text_input("Green threshold", value=row["threshold_green"] or "")
            with col2:
                new_amber = st.text_input("Amber threshold", value=row["threshold_amber"] or "")
            with col3:
                new_red = st.text_input("Red threshold", value=row["threshold_red"] or "")
            new_status = st.selectbox(
                "Status", statuses, index=statuses.index(row["kri_status"]) if row["kri_status"] in statuses else 0
            )
            save = st.form_submit_button("Save changes", type="primary")

            if save:
                user = current_user_email()
                set_values = {
                    "threshold_green": new_green.strip() or None,
                    "threshold_amber": new_amber.strip() or None,
                    "threshold_red": new_red.strip() or None,
                    "kri_status": new_status,
                    "updated_by": user,
                    "updated_at": now_utc(),
                }
                run_statement(build_update(TBL_CATALOG, set_values, {"kri_id": int(selected_id)}))
                log_change(
                    table_name="kri_catalog",
                    record_key=int(selected_id),
                    action="UPDATE",
                    changed_by=user,
                    before=row.to_dict(),
                    after={**row.to_dict(), **set_values},
                )
                st.success("KRI updated.")
                st.cache_data.clear()
