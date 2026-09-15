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
from utils.forms import bump_and_rerun, form_gen, render_pending_banner, show_message
from utils.validation import (
    UNIT_FORMAT_HINTS,
    missing_required_fields,
    validate_kri_title,
    validate_threshold,
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
    gen = form_gen("add_kri")
    with st.form(f"add_kri_form_{gen}"):
        banner = st.empty()

        col1, col2, col3 = st.columns(3)
        with col1:
            entity = st.selectbox("Entity", entities, key=f"add_kri_entity_{gen}")
        with col2:
            department = st.selectbox("Department", departments, key=f"add_kri_department_{gen}")
        with col3:
            risk_category = st.selectbox(
                "Risk category", risk_categories, key=f"add_kri_risk_category_{gen}"
            )

        kri_title = st.text_input("KRI title", key=f"add_kri_title_{gen}")
        description = st.text_area(
            "Description / calculation formula", height=100, key=f"add_kri_description_{gen}"
        )

        col4, col5 = st.columns(2)
        with col4:
            frequency = st.selectbox("Frequency", frequencies, key=f"add_kri_frequency_{gen}")
        with col5:
            unit_of_measure = st.selectbox("Unit of measure", units, key=f"add_kri_unit_{gen}")

        data_source = st.text_input(
            "Data source / point of contact", key=f"add_kri_data_source_{gen}"
        )

        if unit_of_measure and unit_of_measure != "Status / Narrative":
            hint = UNIT_FORMAT_HINTS.get(unit_of_measure, "a plain number, optionally with %")
            st.caption(
                f"Thresholds for **{unit_of_measure}**: each value must be {hint}. "
                f"A range like \">=75%-90%\" is fine; the left side must be lower than the right."
            )
        elif unit_of_measure == "Status / Narrative":
            st.caption("Thresholds for **Status / Narrative** KRIs are free text, e.g. \"On-time\".")

        col6, col7, col8 = st.columns(3)
        with col6:
            threshold_green = st.text_input("Green threshold", key=f"add_kri_green_{gen}")
        with col7:
            threshold_amber = st.text_input("Amber threshold", key=f"add_kri_amber_{gen}")
        with col8:
            threshold_red = st.text_input("Red threshold", key=f"add_kri_red_{gen}")

        date_approved = st.date_input(
            "Date approved", value=date.today(), key=f"add_kri_date_{gen}"
        )

        submitted = st.form_submit_button("Add KRI", type="primary")
        bottom_banner = st.empty()
        render_pending_banner("add_kri", banner, bottom_banner)

        if submitted:
            errors = []

            missing = missing_required_fields(
                {
                    "Entity": entity,
                    "Department": department,
                    "Risk category": risk_category,
                    "KRI title": kri_title,
                    "Description": description,
                    "Frequency": frequency,
                    "Unit of measure": unit_of_measure,
                    "Data source / point of contact": data_source,
                    "Green threshold": threshold_green,
                    "Amber threshold": threshold_amber,
                    "Red threshold": threshold_red,
                    "Date approved": date_approved,
                }
            )
            if missing:
                errors.append(f"Missing/blank required field(s): {', '.join(missing)}.")

            if "KRI title" not in missing:
                title_error = validate_kri_title(kri_title)
                if title_error:
                    errors.append(title_error)

            for label, value in [
                ("Green", threshold_green),
                ("Amber", threshold_amber),
                ("Red", threshold_red),
            ]:
                if f"{label} threshold" not in missing:
                    threshold_error = validate_threshold(label, value, unit_of_measure)
                    if threshold_error:
                        errors.append(threshold_error)

            if errors:
                show_message("error", "\n".join(f"- {e}" for e in errors), banner, bottom_banner)
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
                st.cache_data.clear()
                bump_and_rerun("add_kri", f"KRI '{kri_title.strip()}' added.")

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
