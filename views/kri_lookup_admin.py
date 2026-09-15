import streamlit as st

from utils.audit import log_change
from utils.db import (
    TBL_LOOKUP,
    build_insert,
    build_update,
    current_user_email,
    now_utc,
    run_query,
    run_statement,
    sql_literal,
)

st.header("Lookup Values", divider=True)
st.write(
    "Manage the standardized dropdown values (entity, department, risk category, "
    "frequency, unit of measure) used across the KRI app. Keeping these centralized "
    "avoids free-text spelling drift between departments."
)

lookup_types_df = run_query(f"SELECT DISTINCT lookup_type FROM {TBL_LOOKUP} ORDER BY lookup_type")
lookup_type = st.selectbox("Lookup type", lookup_types_df["lookup_type"].tolist())

values_df = run_query(
    f"SELECT lookup_value, sort_order, is_active FROM {TBL_LOOKUP} "
    f"WHERE lookup_type = {sql_literal(lookup_type)} ORDER BY sort_order, lookup_value"
)
st.dataframe(values_df, use_container_width=True, hide_index=True)

col1, col2 = st.columns(2)

with col1:
    with st.form("add_lookup_value", clear_on_submit=True):
        st.subheader("Add a value")
        new_value = st.text_input("Value")
        new_sort = st.number_input("Sort order", min_value=0, value=int(values_df["sort_order"].max() + 1) if not values_df.empty else 1)
        add_submitted = st.form_submit_button("Add")
        if add_submitted:
            if not new_value.strip():
                st.error("Value is required.")
            else:
                user = current_user_email()
                row = {
                    "lookup_type": lookup_type,
                    "lookup_value": new_value.strip(),
                    "sort_order": int(new_sort),
                    "is_active": True,
                    "created_by": user,
                    "created_at": now_utc(),
                }
                run_statement(build_insert(TBL_LOOKUP, row))
                log_change(
                    table_name="kri_lookup_values",
                    record_key=f"{lookup_type}:{new_value.strip()}",
                    action="INSERT",
                    changed_by=user,
                    after=row,
                )
                st.success(f"Added '{new_value}'.")
                st.cache_data.clear()

with col2:
    with st.form("deactivate_lookup_value"):
        st.subheader("Deactivate a value")
        active_values = values_df[values_df["is_active"]]["lookup_value"].tolist()
        value_to_deactivate = st.selectbox("Value", active_values) if active_values else None
        deactivate_submitted = st.form_submit_button("Deactivate")
        if deactivate_submitted and value_to_deactivate:
            user = current_user_email()
            run_statement(
                build_update(
                    TBL_LOOKUP,
                    {"is_active": False},
                    {"lookup_type": lookup_type, "lookup_value": value_to_deactivate},
                )
            )
            log_change(
                table_name="kri_lookup_values",
                record_key=f"{lookup_type}:{value_to_deactivate}",
                action="UPDATE",
                changed_by=user,
                after={"is_active": False},
            )
            st.success(f"Deactivated '{value_to_deactivate}'.")
            st.cache_data.clear()
