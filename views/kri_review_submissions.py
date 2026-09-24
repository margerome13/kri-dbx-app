from datetime import date

import streamlit as st

from config.user_roles import get_user_role
from utils.access import require_page_access
from utils.db import (
    TBL_CATALOG,
    TBL_SUBMISSIONS,
    current_user_email,
    fetch_lookup,
    run_query,
    sql_literal,
)
from utils.department_scope import catalog_department_clause, is_global_viewer, require_scoped_department
from utils.review_actions import render_approve_reject_forms, render_submission_summary

HISTORY_SELECT = """
    s.submission_id, s.reporting_period, s.actual_value_text, s.rag_status,
    s.remarks, s.review_notes, s.submitted_by, s.submitted_at,
    s.approved_by, s.approved_at, s.updated_by, s.updated_at,
    s.workflow_status, c.entity, c.department, c.kri_title
"""

require_page_access("review_submissions")

user = current_user_email()
role = get_user_role(user)
is_admin = is_global_viewer(user)

st.header("Review Submitted KRIs", divider=True)
if is_admin:
    st.write(
        "RCO program view: monitor the **program queue** across all departments, act on "
        "**pending** submissions, or review your own approval/rejection history."
    )
else:
    st.write(
        "Approve or reject KRI submissions from your department. You cannot edit the "
        "Maker's value or remarks — only approve, reject with a reason, or review your "
        "past decisions."
    )

if role == "CHECKER":
    require_scoped_department(user)

dept_clause = catalog_department_clause(user, alias="c")
user_lit = sql_literal(user)

tab_labels = ["Program queue", "Pending review", "My approvals", "My rejections"] if is_admin else [
    "Pending review",
    "My approvals",
    "My rejections",
]
tabs = st.tabs(tab_labels)
tab_by_name = dict(zip(tab_labels, tabs))

if is_admin:
    with tab_by_name["Program queue"]:
        entities = fetch_lookup("entity")
        departments = fetch_lookup("department")
        f1, f2, f3, f4, f5 = st.columns(5)
        with f1:
            pq_entity = st.selectbox("Entity", ["All"] + entities, key="pq_entity")
        with f2:
            pq_dept = st.selectbox("Department", ["All"] + departments, key="pq_dept")
        with f3:
            pq_workflow = st.selectbox(
                "Workflow status",
                ["Submitted", "Approved", "Rejected", "All"],
                key="pq_workflow",
            )
        with f4:
            pq_lookback = st.selectbox(
                "Submitted in last",
                [3, 6, 12, 24],
                index=1,
                format_func=lambda m: f"{m} months",
                key="pq_lookback",
            )
        with f5:
            pq_period_only = st.checkbox("One reporting period", key="pq_period_only")
        pq_period = None
        if pq_period_only:
            pq_period = st.date_input(
                "Reporting period",
                value=date.today().replace(day=1),
                key="pq_period",
            )
            pq_period = date(pq_period.year, pq_period.month, 1)

        pq_clauses = [
            f"s.submitted_at >= add_months(current_timestamp(), -{int(pq_lookback)})",
        ]
        if pq_entity != "All":
            pq_clauses.append(f"c.entity = {sql_literal(pq_entity)}")
        if pq_dept != "All":
            pq_clauses.append(f"c.department = {sql_literal(pq_dept)}")
        if pq_workflow != "All":
            pq_clauses.append(f"s.workflow_status = {sql_literal(pq_workflow)}")
        if pq_period is not None:
            pq_clauses.append(f"s.reporting_period = {sql_literal(pq_period)}")
        pq_where = " AND ".join(pq_clauses)

        program_df = run_query(
            f"SELECT {HISTORY_SELECT} "
            f"FROM {TBL_SUBMISSIONS} s "
            f"INNER JOIN {TBL_CATALOG} c ON s.kri_id = c.kri_id "
            f"WHERE {pq_where} "
            f"ORDER BY CASE s.workflow_status WHEN 'Submitted' THEN 0 WHEN 'Rejected' THEN 1 ELSE 2 END, "
            f"s.submitted_at DESC, c.department, c.kri_title"
        )

        pending_n = int((program_df["workflow_status"] == "Submitted").sum()) if not program_df.empty else 0
        m1, m2, m3 = st.columns(3)
        m1.metric("Pending approval (in view)", pending_n)
        m2.metric("Rows in queue", len(program_df))
        m3.metric(
            "Departments with pending",
            int(program_df.loc[program_df["workflow_status"] == "Submitted", "department"].nunique())
            if not program_df.empty
            else 0,
        )

        if program_df.empty:
            st.info("No submissions match these filters.")
        else:
            st.dataframe(
                program_df[
                    [
                        "workflow_status",
                        "submitted_at",
                        "entity",
                        "department",
                        "kri_title",
                        "reporting_period",
                        "actual_value_text",
                        "rag_status",
                        "submitted_by",
                        "approved_by",
                    ]
                ].rename(
                    columns={
                        "workflow_status": "Status",
                        "submitted_at": "Submitted at",
                        "kri_title": "KRI",
                        "reporting_period": "Period",
                        "actual_value_text": "Value",
                        "rag_status": "RAG",
                        "submitted_by": "Maker",
                        "approved_by": "Approved by",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )

            submitted_only = program_df[program_df["workflow_status"] == "Submitted"]
            if submitted_only.empty:
                st.caption("No **Submitted** rows in this view — adjust filters or use **Pending review**.")
            else:
                st.subheader("Act on a pending submission", divider="gray")
                labels = [
                    f"{r['department']} · {r['kri_title']} · {r['reporting_period']}"
                    for _, r in submitted_only.iterrows()
                ]
                pick = st.selectbox(
                    "Choose submission",
                    range(len(labels)),
                    format_func=lambda i: labels[i],
                    key="pq_action_choice",
                )
                action_row = submitted_only.iloc[pick]
                render_submission_summary(action_row)
                render_approve_reject_forms(action_row, user, key_prefix="pq")

with tab_by_name["Pending review"]:
    queue_df = run_query(
        f"SELECT {HISTORY_SELECT} "
        f"FROM {TBL_SUBMISSIONS} s "
        f"INNER JOIN {TBL_CATALOG} c ON s.kri_id = c.kri_id "
        f"WHERE s.workflow_status = 'Submitted'{dept_clause} "
        f"ORDER BY s.submitted_at ASC, c.kri_title"
    )

    if queue_df.empty:
        st.success("No submissions waiting for review.")
    else:
        scope = "all departments" if is_admin else "your department"
        st.caption(f"{len(queue_df)} submission(s) with status **Submitted** ({scope}).")
        labels = [
            f"{row['entity']} · {row['department']} · {row['kri_title']} · "
            f"{row['reporting_period']} (by {row['submitted_by']})"
            for _, row in queue_df.iterrows()
        ]
        choice = st.selectbox(
            "Select a submission to review",
            range(len(labels)),
            format_func=lambda i: labels[i],
            key="review_queue_choice",
        )
        row = queue_df.iloc[choice]
        render_submission_summary(row)
        render_approve_reject_forms(row, user, key_prefix="pending")

with tab_by_name["My approvals"]:
    lookback = st.selectbox(
        "Show approvals from the last",
        [3, 6, 12, 24],
        index=1,
        format_func=lambda m: f"{m} months",
        key="review_approved_lookback",
    )
    approved_df = run_query(
        f"SELECT {HISTORY_SELECT} "
        f"FROM {TBL_SUBMISSIONS} s "
        f"INNER JOIN {TBL_CATALOG} c ON s.kri_id = c.kri_id "
        f"WHERE s.workflow_status = 'Approved' "
        f"AND LOWER(s.approved_by) = LOWER({user_lit}) "
        f"AND s.approved_at >= add_months(current_timestamp(), -{int(lookback)}) "
        f"{dept_clause} "
        f"ORDER BY s.approved_at DESC, c.kri_title"
    )
    st.caption(
        f"KRIs you **approved** as **{user}** "
        f"(most recent {lookback} months, your department scope)."
    )
    if approved_df.empty:
        st.info("No approvals recorded for you in this window.")
    else:
        st.dataframe(
            approved_df[
                [
                    "approved_at",
                    "entity",
                    "department",
                    "kri_title",
                    "reporting_period",
                    "actual_value_text",
                    "rag_status",
                    "submitted_by",
                    "review_notes",
                ]
            ].rename(
                columns={
                    "approved_at": "Approved at",
                    "kri_title": "KRI",
                    "reporting_period": "Reporting period",
                    "actual_value_text": "Actual value",
                    "rag_status": "RAG",
                    "submitted_by": "Submitted by",
                    "review_notes": "Your note",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

with tab_by_name["My rejections"]:
    lookback_r = st.selectbox(
        "Show rejections from the last",
        [3, 6, 12, 24],
        index=1,
        format_func=lambda m: f"{m} months",
        key="review_rejected_lookback",
    )
    rejected_df = run_query(
        f"SELECT {HISTORY_SELECT} "
        f"FROM {TBL_SUBMISSIONS} s "
        f"INNER JOIN {TBL_CATALOG} c ON c.kri_id = c.kri_id "
        f"WHERE s.workflow_status = 'Rejected' "
        f"AND LOWER(s.updated_by) = LOWER({user_lit}) "
        f"AND s.updated_at >= add_months(current_timestamp(), -{int(lookback_r)}) "
        f"{dept_clause} "
        f"ORDER BY s.updated_at DESC, c.kri_title"
    )
    st.caption(
        f"KRIs you **rejected** as **{user}** "
        f"(most recent {lookback_r} months, your department scope)."
    )
    if rejected_df.empty:
        st.info("No rejections recorded for you in this window.")
    else:
        st.dataframe(
            rejected_df[
                [
                    "updated_at",
                    "entity",
                    "department",
                    "kri_title",
                    "reporting_period",
                    "actual_value_text",
                    "rag_status",
                    "submitted_by",
                    "review_notes",
                ]
            ].rename(
                columns={
                    "updated_at": "Rejected at",
                    "kri_title": "KRI",
                    "reporting_period": "Reporting period",
                    "actual_value_text": "Actual value",
                    "rag_status": "RAG",
                    "submitted_by": "Submitted by",
                    "review_notes": "Rejection reason",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
