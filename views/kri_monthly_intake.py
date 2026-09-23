from datetime import date

import streamlit as st

from config.user_roles import get_user_role
from utils.access import require_page_access
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
from utils.department_scope import (
    assert_department_allowed,
    require_scoped_department,
    scoped_department,
)
from utils.forms import bump_and_rerun, render_pending_banner, show_message
from utils.validation import (
    UNIT_FORMAT_HINTS,
    parse_reported_number,
    parse_threshold_bounds,
    resolve_rag_status,
    validate_actual_value,
)

RAG_EMOJI = {"Green": "🟢", "Amber": "🟠", "Red": "🔴"}

require_page_access("monthly_intake")

user = current_user_email()
role = get_user_role(user)

st.header("Submit / Edit Monthly KRI", divider=True)
st.write(
    "Standardized monthly intake for department Key Risk Indicators. Select your KRI "
    "and reporting month below — if a submission already exists for that month it "
    "will load for editing instead of creating a duplicate."
)

if role == "MAKER":
    require_scoped_department(user)

user_dept = scoped_department(user)

entities = fetch_lookup("entity")
col1, col2 = st.columns(2)
with col1:
    entity = st.selectbox("Entity", entities)
with col2:
    dept_filter = f" AND department = {sql_literal(user_dept)}" if user_dept else ""
    departments_df = run_query(
        f"SELECT DISTINCT department FROM {TBL_CATALOG} "
        f"WHERE entity = {sql_literal(entity)} AND kri_status = 'Active'{dept_filter} "
        f"ORDER BY department"
    )
    dept_list = departments_df["department"].tolist() if not departments_df.empty else []
    if user_dept:
        department = user_dept
        st.text_input("Department", value=department, disabled=True)
    else:
        department = st.selectbox("Department", dept_list)

if not department:
    st.info("No active KRIs are defined yet for this entity/department. Add one in "
             "**Administration → Add a KRI** first.")
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
workflow = None if existing is None else str(existing["workflow_status"])

if existing is not None:
    st.caption(
        f"Existing submission (workflow: **{workflow}**, "
        f"last updated {existing['updated_at'] or existing['submitted_at']})."
    )
    if workflow == "Rejected" and existing.get("review_notes"):
        st.warning(f"Checker feedback: {existing['review_notes']}")

maker_locked = role == "MAKER" and workflow == "Approved"
if maker_locked:
    st.info(
        "This submission is **Approved** and is read-only for Makers. "
        "Contact an RCO **Admin** if a correction is needed."
    )

kri_unit = kri_row["unit_of_measure"]
if kri_unit and kri_unit != "Status / Narrative":
    st.caption(f"Expected format for **{kri_unit}**: {UNIT_FORMAT_HINTS.get(kri_unit, 'a plain number, optionally with %')}.")

read_only = maker_locked

actual_value_text = st.text_input(
    f"Actual value ({kri_unit or 'as reported'})",
    value="" if existing is None else str(existing["actual_value_text"] or ""),
    key="kri_intake_actual_value",
    disabled=read_only,
)

actual_numeric = parse_reported_number(actual_value_text) if actual_value_text.strip() else None
green_bounds = parse_threshold_bounds(kri_row["threshold_green"], kri_unit)
amber_bounds = parse_threshold_bounds(kri_row["threshold_amber"], kri_unit)
red_bounds = parse_threshold_bounds(kri_row["threshold_red"], kri_unit)
resolved_rag = resolve_rag_status(actual_numeric, green_bounds, amber_bounds, red_bounds)

if resolved_rag:
    st.markdown(
        f"**RAG status:** {RAG_EMOJI[resolved_rag]} {resolved_rag} "
        "*(auto-computed from the Actual value against this KRI's thresholds)*"
    )
    rag_status = resolved_rag
elif actual_value_text.strip():
    st.caption(
        "RAG status can't be auto-computed from this Actual value and the KRI's "
        "thresholds — select it manually."
    )
    rag_status = st.radio(
        "RAG status",
        ["Green", "Amber", "Red"],
        index=0 if existing is None else ["Green", "Amber", "Red"].index(existing["rag_status"]),
        horizontal=True,
        key="kri_intake_rag_manual",
        disabled=read_only,
    )
else:
    rag_status = None

if not read_only:
    with st.form("kri_submission_form"):
        banner = st.empty()

        remarks = st.text_area(
            "Remarks (cause, action items, target date) — required for Amber/Red",
            value="" if existing is None else str(existing["remarks"] or ""),
            height=150,
        )
        submitted = st.form_submit_button("Save submission", type="primary")
        bottom_banner = st.empty()
        render_pending_banner("kri_submission", banner, bottom_banner)

        if submitted:
            errors = []
            if not assert_department_allowed(user, department):
                errors.append("You are not allowed to submit for this department.")
            if not actual_value_text.strip():
                errors.append("Actual value is required.")
            else:
                value_error = validate_actual_value("Actual value", actual_value_text, kri_unit)
                if value_error:
                    errors.append(value_error)
            if actual_value_text.strip() and not rag_status:
                errors.append(
                    "RAG status could not be determined for this Actual value — check "
                    "it against the KRI's thresholds above."
                )
            if rag_status in ("Amber", "Red") and not remarks.strip():
                errors.append("Remarks are required when RAG status is Amber or Red.")

            if errors:
                show_message("error", "\n".join(f"- {e}" for e in errors), banner, bottom_banner)
            else:
                ts = now_utc()
                if role == "ADMIN" and workflow == "Approved":
                    new_workflow = "Approved"
                    approved_by = existing["approved_by"]
                    approved_at = existing["approved_at"]
                    review_notes = existing.get("review_notes")
                elif workflow == "Rejected":
                    new_workflow = "Submitted"
                    approved_by = None
                    approved_at = None
                    review_notes = None
                    submitted_at = ts
                    submitted_by = user
                else:
                    new_workflow = "Submitted"
                    approved_by = existing["approved_by"] if existing is not None else None
                    approved_at = existing["approved_at"] if existing is not None else None
                    review_notes = existing.get("review_notes") if existing is not None else None
                    submitted_at = existing["submitted_at"] if existing is not None else ts
                    submitted_by = existing["submitted_by"] if existing is not None else user

                if workflow != "Rejected":
                    submitted_at = existing["submitted_at"] if existing is not None else ts
                    submitted_by = existing["submitted_by"] if existing is not None else user

                row = {
                    "submission_id": existing["submission_id"] if existing is not None else new_id(),
                    "kri_id": kri_id,
                    "reporting_period": period_first_of_month,
                    "actual_value_text": actual_value_text.strip(),
                    "actual_value_numeric": actual_numeric,
                    "rag_status": rag_status,
                    "remarks": remarks.strip() or None,
                    "workflow_status": new_workflow,
                    "review_notes": review_notes,
                    "submitted_by": submitted_by,
                    "submitted_at": submitted_at,
                    "approved_by": approved_by,
                    "approved_at": approved_at,
                    "updated_by": user,
                    "updated_at": ts,
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
