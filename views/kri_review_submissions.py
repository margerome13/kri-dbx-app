import streamlit as st

from config.user_roles import get_user_role
from utils.access import require_page_access
from utils.audit import log_change
from utils.db import (
    TBL_CATALOG,
    TBL_SUBMISSIONS,
    build_update,
    current_user_email,
    now_utc,
    run_query,
    run_statement,
)
from utils.department_scope import catalog_department_clause, is_global_viewer, require_scoped_department
from utils.forms import bump_and_rerun, render_pending_banner, show_message

RAG_EMOJI = {"Green": "🟢", "Amber": "🟠", "Red": "🔴"}

require_page_access("review_submissions")

user = current_user_email()
role = get_user_role(user)

st.header("Review Submitted KRIs", divider=True)
st.write(
    "Approve or reject monthly KRI submissions from your department. You cannot edit "
    "the Maker's actual value or remarks — only the workflow decision."
)

if role == "CHECKER":
    require_scoped_department(user)

dept_clause = catalog_department_clause(user, alias="c")
queue_df = run_query(
    f"SELECT s.submission_id, s.reporting_period, s.actual_value_text, s.rag_status, "
    f"s.remarks, s.submitted_by, s.submitted_at, c.entity, c.department, c.kri_title "
    f"FROM {TBL_SUBMISSIONS} s "
    f"INNER JOIN {TBL_CATALOG} c ON s.kri_id = c.kri_id "
    f"WHERE s.workflow_status = 'Submitted'{dept_clause} "
    f"ORDER BY s.submitted_at ASC, c.kri_title"
)

if queue_df.empty:
    st.success("No submissions waiting for review.")
    st.stop()

st.subheader("Queue", divider="gray")
st.caption(f"{len(queue_df)} submission(s) with status **Submitted**.")

labels = [
    f"{row['entity']} · {row['department']} · {row['kri_title']} · "
    f"{row['reporting_period']} (by {row['submitted_by']})"
    for _, row in queue_df.iterrows()
]
choice = st.selectbox("Select a submission to review", range(len(labels)), format_func=lambda i: labels[i])
row = queue_df.iloc[choice]

st.markdown(
    f"**KRI:** {row['kri_title']}  \n"
    f"**Entity / department:** {row['entity']} / {row['department']}  \n"
    f"**Reporting month:** {row['reporting_period']}  \n"
    f"**Submitted by:** {row['submitted_by']} at {row['submitted_at']}"
)
st.markdown(
    f"**Actual value:** {row['actual_value_text']}  \n"
    f"**RAG:** {RAG_EMOJI.get(row['rag_status'], '')} {row['rag_status']}  \n"
    f"**Maker remarks:** {row['remarks'] or '—'}"
)

col_approve, col_reject = st.columns(2)

with col_approve:
    with st.form("review_approve_form"):
        approve_banner = st.empty()
        approve_notes = st.text_area(
            "Checker note (optional on approve)",
            height=80,
            key="review_approve_notes",
        )
        approve_clicked = st.form_submit_button("Approve", type="primary")
        approve_bottom = st.empty()
        render_pending_banner("review_approve", approve_banner, approve_bottom)
        if approve_clicked:
            ts = now_utc()
            after = {
                "workflow_status": "Approved",
                "review_notes": approve_notes.strip() or None,
                "approved_by": user,
                "approved_at": ts,
                "updated_by": user,
                "updated_at": ts,
            }
            run_statement(
                build_update(
                    TBL_SUBMISSIONS,
                    after,
                    {"submission_id": row["submission_id"]},
                )
            )
            log_change(
                table_name="kri_monthly_submissions",
                record_key=row["submission_id"],
                action="UPDATE",
                changed_by=user,
                before=row.to_dict(),
                after={**row.to_dict(), **after},
            )
            bump_and_rerun("review_approve", "Submission approved.", bump=False)

with col_reject:
    with st.form("review_reject_form"):
        reject_banner = st.empty()
        reject_notes = st.text_area(
            "Rejection reason (required)",
            height=80,
            key="review_reject_notes",
        )
        reject_clicked = st.form_submit_button("Reject", type="primary")
        reject_bottom = st.empty()
        render_pending_banner("review_reject", reject_banner, reject_bottom)
        if reject_clicked:
            if not reject_notes.strip():
                show_message(
                    "error",
                    "A rejection reason is required.",
                    reject_banner,
                    reject_bottom,
                )
            else:
                ts = now_utc()
                after = {
                    "workflow_status": "Rejected",
                    "review_notes": reject_notes.strip(),
                    "approved_by": None,
                    "approved_at": None,
                    "updated_by": user,
                    "updated_at": ts,
                }
                run_statement(
                    build_update(
                        TBL_SUBMISSIONS,
                        after,
                        {"submission_id": row["submission_id"]},
                    )
                )
                log_change(
                    table_name="kri_monthly_submissions",
                    record_key=row["submission_id"],
                    action="UPDATE",
                    changed_by=user,
                    before=row.to_dict(),
                    after={**row.to_dict(), **after},
                )
                bump_and_rerun("review_reject", "Submission rejected.", bump=False)

if is_global_viewer(user):
    st.caption("As **ADMIN**, you see submissions for all departments.")
