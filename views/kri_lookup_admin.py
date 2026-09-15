import streamlit as st

from utils.audit import log_change
from utils.db import (
    TBL_LOOKUP,
    build_insert,
    build_update,
    cascade_rename_lookup_value,
    current_user_email,
    next_lookup_id,
    now_utc,
    run_query,
    run_statement,
    sql_literal,
)
from utils.forms import bump_and_rerun, form_gen, render_pending_banner

st.header("Lookup Values", divider=True)
st.write(
    "Manage the standardized dropdown values (entity, department, risk category, "
    "frequency, unit of measure) used across the KRI app. Keeping these centralized "
    "avoids free-text spelling drift between departments."
)

lookup_types_df = run_query(f"SELECT DISTINCT lookup_type FROM {TBL_LOOKUP} ORDER BY lookup_type")
lookup_type = st.selectbox("Lookup type", lookup_types_df["lookup_type"].tolist())

values_df = run_query(
    f"SELECT id, lookup_value, is_active FROM {TBL_LOOKUP} "
    f"WHERE lookup_type = {sql_literal(lookup_type)} ORDER BY id"
)
st.dataframe(values_df, use_container_width=True, hide_index=True)

tab_add, tab_edit, tab_deactivate = st.tabs(["Add a value", "Edit a value", "Deactivate a value"])

with tab_add:
    next_id = next_lookup_id(lookup_type)
    st.caption(f"This value will be assigned **id {next_id}** within '{lookup_type}' — ids are auto-assigned and cannot be edited.")

    gen = form_gen("add_lookup")
    with st.form(f"add_lookup_value_{gen}"):
        banner = st.empty()
        render_pending_banner("add_lookup", banner)

        new_value = st.text_input("Value", key=f"add_lookup_value_input_{gen}")
        add_submitted = st.form_submit_button("Add")
        if add_submitted:
            if not new_value.strip():
                banner.error("Value is required.")
            elif new_value.strip() in values_df["lookup_value"].tolist():
                banner.error(f"'{new_value.strip()}' already exists for '{lookup_type}'.")
            else:
                user = current_user_email()
                row = {
                    "lookup_type": lookup_type,
                    "id": next_id,
                    "lookup_value": new_value.strip(),
                    "is_active": True,
                    "created_by": user,
                    "created_at": now_utc(),
                }
                run_statement(build_insert(TBL_LOOKUP, row))
                log_change(
                    table_name="kri_lookup_values",
                    record_key=f"{lookup_type}:{next_id}",
                    action="INSERT",
                    changed_by=user,
                    after=row,
                )
                st.cache_data.clear()
                bump_and_rerun("add_lookup", f"Added '{new_value.strip()}' as id {next_id}.")

with tab_edit:
    st.write(
        "Use this when a value's name changes (e.g. a department is renamed) without "
        "losing its identity. The rename is also applied to any existing KRI catalog "
        "or submission rows that already used the old text."
    )
    if values_df.empty:
        st.info("No values to edit yet.")
    else:
        editable_id = st.selectbox(
            "Value to rename",
            values_df["id"].tolist(),
            format_func=lambda vid: f"{vid} — {values_df.loc[values_df['id'] == vid, 'lookup_value'].iloc[0]}",
            key="edit_lookup_select",
        )
        current_value = values_df.loc[values_df["id"] == editable_id, "lookup_value"].iloc[0]

        with st.form("edit_lookup_value"):
            edit_banner = st.empty()
            render_pending_banner("edit_lookup", edit_banner)

            st.text_input("ID (auto-assigned, not editable)", value=str(editable_id), disabled=True)
            new_text = st.text_input("Value", value=current_value)
            save = st.form_submit_button("Save rename", type="primary")

            if save:
                new_text = new_text.strip()
                if not new_text:
                    edit_banner.error("Value is required.")
                elif new_text == current_value:
                    edit_banner.info("No change.")
                elif new_text in values_df["lookup_value"].tolist():
                    edit_banner.error(f"'{new_text}' already exists for '{lookup_type}'.")
                else:
                    user = current_user_email()
                    run_statement(
                        build_update(
                            TBL_LOOKUP,
                            {"lookup_value": new_text},
                            {"lookup_type": lookup_type, "id": int(editable_id)},
                        )
                    )
                    cascaded = cascade_rename_lookup_value(lookup_type, current_value, new_text)
                    log_change(
                        table_name="kri_lookup_values",
                        record_key=f"{lookup_type}:{editable_id}",
                        action="UPDATE",
                        changed_by=user,
                        before={"lookup_value": current_value},
                        after={"lookup_value": new_text, "cascaded_to": cascaded},
                    )
                    message = f"Renamed '{current_value}' to '{new_text}'."
                    if cascaded:
                        details = ", ".join(f"{n} row(s) in {t}" for t, n in cascaded.items())
                        message += f" Also updated existing records to match: {details}."
                    st.cache_data.clear()
                    bump_and_rerun("edit_lookup", message, bump=False)

with tab_deactivate:
    active_df = values_df[values_df["is_active"]]
    if active_df.empty:
        st.info("No active values to deactivate.")
    else:
        with st.form("deactivate_lookup_value"):
            deactivate_banner = st.empty()
            render_pending_banner("deactivate_lookup", deactivate_banner)

            id_to_deactivate = st.selectbox(
                "Value",
                active_df["id"].tolist(),
                format_func=lambda vid: f"{vid} — {active_df.loc[active_df['id'] == vid, 'lookup_value'].iloc[0]}",
                key="deactivate_lookup_select",
            )
            deactivate_submitted = st.form_submit_button("Deactivate")
            if deactivate_submitted:
                value_text = active_df.loc[active_df["id"] == id_to_deactivate, "lookup_value"].iloc[0]
                user = current_user_email()
                run_statement(
                    build_update(
                        TBL_LOOKUP,
                        {"is_active": False},
                        {"lookup_type": lookup_type, "id": int(id_to_deactivate)},
                    )
                )
                log_change(
                    table_name="kri_lookup_values",
                    record_key=f"{lookup_type}:{id_to_deactivate}",
                    action="UPDATE",
                    changed_by=user,
                    after={"is_active": False},
                )
                st.cache_data.clear()
                bump_and_rerun("deactivate_lookup", f"Deactivated '{value_text}'.", bump=False)
