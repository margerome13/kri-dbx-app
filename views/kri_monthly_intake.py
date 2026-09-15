from datetime import date

import pandas as pd
import streamlit as st

from utils.audit import log_change
from utils.db import (
    TBL_CATALOG,
    TBL_SUBMISSIONS,
    build_merge_upsert,
    current_user_email,
    fetch_lookup,
    new_id,
    now_utc,
    run_query,
    run_statement,
    sql_literal,
)
from utils.forms import bump_and_rerun, render_pending_banner

st.header("Submit / Edit Monthly KRI", divider=True)
st.write(
    "Standardized monthly intake for department Key Risk Indicators. Select your KRI "
    "and reporting month below — if a submission already exists for that month it "
    "will load for editing instead of creating a duplicate."
)

entities = fetch_lookup("entity")
col1, col2 = st.columns(2)
with col1:
    entity = st.selectbox("Entity", entities)
with col2:
    departments_df = run_query(
        f"SELECT DISTINCT department FROM {TBL_CATALOG} "
        f"WHERE entity = {sql_literal(entity)} AND kri_status = 'Active' ORDER BY department"
    )
    department = st.selectbox(
        "Department", departments_df["department"].tolist() if not departments_df.empty else []
    )

if not department:
    st.info("No active KRIs are defined yet for this entity/department. Add one in "
             "**Administration → KRI Catalog Manager** first.")
    st.stop()

kris_df = run_query(
    f"SELECT kri_id, kri_title, unit_of_measure, threshold_green, threshold_amber, "
    f"threshold_red, frequency FROM {TBL_CATALOG} "
    f"WHERE entity = {sql_literal(entity)} AND department = {sql_literal(department)} "
    f"AND kri_status = 'Active' ORDER BY kri_title"
)

if kris_df.empty:
    st.info("No active KRIs found for this department.")
    st.stop()

kri_title = st.selectbox("KRI", kris_df["kri_title"].tolist())
kri_row = kris_df[kris_df["kri_title"] == kri_title].iloc[0]
kri_id = int(kri_row["kri_id"])

with st.expander("KRI thresholds", expanded=True):
    tcol1, tcol2, tcol3 = st.columns(3)
    tcol1.markdown(f"🟢 **Green**\n\n{kri_row['threshold_green'] or '—'}")
    tcol2.markdown(f"🟠 **Amber**\n\n{kri_row['threshold_amber'] or '—'}")
    tcol3.markdown(f"🔴 **Red**\n\n{kri_row['threshold_red'] or '—'}")

today = date.today()
reporting_period = st.date_input(
    "Reporting month (any day within the month)",
    value=date(today.year, today.month, 1),
)
period_first_of_month = date(reporting_period.year, reporting_period.month, 1)

existing_df = run_query(
    f"SELECT * FROM {TBL_SUBMISSIONS} WHERE kri_id = {kri_id} "
    f"AND reporting_period = {sql_literal(period_first_of_month)}"
)
existing = existing_df.iloc[0] if not existing_df.empty else None

if existing is not None:
    st.caption(
        f"Existing submission found (workflow status: **{existing['workflow_status']}**, "
        f"last updated {existing['updated_at'] or existing['submitted_at']}). Saving will update it."
    )

with st.form("kri_submission_form"):
    banner = st.empty()
    render_pending_banner("kri_submission", banner)

    actual_value_text = st.text_input(
        f"Actual value ({kri_row['unit_of_measure'] or 'as reported'})",
        value="" if existing is None else str(existing["actual_value_text"] or ""),
    )
    rag_status = st.radio(
        "RAG status",
        ["Green", "Amber", "Red"],
        index=0 if existing is None else ["Green", "Amber", "Red"].index(existing["rag_status"]),
        horizontal=True,
    )
    remarks = st.text_area(
        "Remarks (cause, action items, target date) — required for Amber/Red",
        value="" if existing is None else str(existing["remarks"] or ""),
        height=150,
    )
    submitted = st.form_submit_button("Save submission", type="primary")

    if submitted:
        errors = []
        if not actual_value_text.strip():
            errors.append("Actual value is required.")
        if rag_status in ("Amber", "Red") and not remarks.strip():
            errors.append("Remarks are required when RAG status is Amber or Red.")

        if errors:
            banner.error("\n".join(f"- {e}" for e in errors))
        else:
            try:
                numeric_value = pd.to_numeric(
                    actual_value_text.replace("%", "").replace(",", ""), errors="coerce"
                )
                numeric_value = None if pd.isna(numeric_value) else float(numeric_value)
            except Exception:
                numeric_value = None

            user = current_user_email()
            row = {
                "submission_id": existing["submission_id"] if existing is not None else new_id(),
                "kri_id": kri_id,
                "reporting_period": period_first_of_month,
                "actual_value_text": actual_value_text.strip(),
                "actual_value_numeric": numeric_value,
                "rag_status": rag_status,
                "remarks": remarks.strip() or None,
                "workflow_status": "Submitted",
                "submitted_by": existing["submitted_by"] if existing is not None else user,
                "submitted_at": existing["submitted_at"] if existing is not None else now_utc(),
                "approved_by": existing["approved_by"] if existing is not None else None,
                "approved_at": existing["approved_at"] if existing is not None else None,
                "updated_by": user,
                "updated_at": now_utc(),
            }
            run_statement(
                build_merge_upsert(TBL_SUBMISSIONS, row, key_columns=["submission_id"])
            )
            log_change(
                table_name="kri_monthly_submissions",
                record_key=row["submission_id"],
                action="UPDATE" if existing is not None else "INSERT",
                changed_by=user,
                before=None if existing is None else existing.to_dict(),
                after=row,
            )
            st.cache_data.clear()
            bump_and_rerun("kri_submission", "Submission saved.", bump=False)
