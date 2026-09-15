import streamlit as st

from utils.access import require_page_access
from utils.audit import log_change
from utils.db import (
    TBL_CATALOG,
    build_update,
    current_user_email,
    fetch_lookup,
    now_utc,
    run_query,
    run_statement,
    sql_literal,
)
from utils.forms import bump_and_rerun, render_pending_banner, show_message
from utils.validation import UNIT_FORMAT_HINTS, validate_threshold

require_page_access("catalog_manage")

st.header("Manage Existing KRIs", divider=True)
st.write("Review KRIs already in the catalog, and update their thresholds or status.")

entities = fetch_lookup("entity")
statuses = fetch_lookup("kri_status")

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
        edit_banner = st.empty()

        edit_unit = row["unit_of_measure"]
        if edit_unit and edit_unit != "Status / Narrative":
            hint = UNIT_FORMAT_HINTS.get(edit_unit, "a plain number, optionally with %")
            st.caption(f"Thresholds for **{edit_unit}**: each value must be {hint}.")
        elif edit_unit == "Status / Narrative":
            st.caption("Thresholds for **Status / Narrative** KRIs are free text, e.g. \"On-time\".")

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
        edit_bottom_banner = st.empty()
        render_pending_banner("edit_kri", edit_banner, edit_bottom_banner)

        if save:
            errors = []
            for label, value in [
                ("Green", new_green),
                ("Amber", new_amber),
                ("Red", new_red),
            ]:
                if value.strip():
                    threshold_error = validate_threshold(label, value, edit_unit)
                    if threshold_error:
                        errors.append(threshold_error)

            if errors:
                show_message(
                    "error", "\n".join(f"- {e}" for e in errors), edit_banner, edit_bottom_banner
                )
            else:
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
                st.cache_data.clear()
                bump_and_rerun("edit_kri", "KRI updated.", bump=False)
