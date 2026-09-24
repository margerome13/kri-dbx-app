"""Shared approve / reject actions for the review workflow."""
import streamlit as st

from utils.audit import log_change
from utils.db import TBL_SUBMISSIONS, build_update, now_utc, run_statement
from utils.forms import bump_and_rerun, render_pending_banner, show_message

RAG_EMOJI = {"Green": "🟢", "Amber": "🟠", "Red": "🔴"}


def render_submission_summary(row) -> None:
    st.markdown(
        f"**KRI:** {row['kri_title']}  \n"
        f"**Entity / department:** {row['entity']} / {row['department']}  \n"
        f"**Reporting period:** {row['reporting_period']}  \n"
        f"**Workflow:** {row['workflow_status']}  \n"
        f"**Submitted by:** {row['submitted_by']} at {row['submitted_at']}"
    )
    st.markdown(
        f"**Actual value:** {row['actual_value_text']}  \n"
        f"**RAG:** {RAG_EMOJI.get(row['rag_status'], '')} {row['rag_status']}  \n"
        f"**Maker remarks:** {row['remarks'] or '—'}"
    )
    if row.get("review_notes"):
        st.markdown(f"**Review notes:** {row['review_notes']}")


def render_approve_reject_forms(row, user: str, *, key_prefix: str) -> None:
    col_approve, col_reject = st.columns(2)

    with col_approve:
        with st.form(f"{key_prefix}_approve_form"):
            approve_banner = st.empty()
            approve_notes = st.text_area(
                "Checker note (optional on approve)",
                height=80,
                key=f"{key_prefix}_approve_notes",
            )
            approve_clicked = st.form_submit_button("Approve", type="primary")
            approve_bottom = st.empty()
            render_pending_banner(f"{key_prefix}_approve", approve_banner, approve_bottom)
            if approve_clicked:
                _approve(row, user, approve_notes, key_prefix)

    with col_reject:
        with st.form(f"{key_prefix}_reject_form"):
            reject_banner = st.empty()
            reject_notes = st.text_area(
                "Rejection reason (required)",
                height=80,
                key=f"{key_prefix}_reject_notes",
            )
            reject_clicked = st.form_submit_button("Reject", type="primary")
            reject_bottom = st.empty()
            render_pending_banner(f"{key_prefix}_reject", reject_banner, reject_bottom)
            if reject_clicked:
                if not reject_notes.strip():
                    show_message(
                        "error",
                        "A rejection reason is required.",
                        reject_banner,
                        reject_bottom,
                    )
                else:
                    _reject(row, user, reject_notes, key_prefix)


def _approve(row, user: str, approve_notes: str, key_prefix: str) -> None:
    ts = now_utc()
    after = {
        "workflow_status": "Approved",
        "review_notes": approve_notes.strip() or None,
        "approved_by": user,
        "approved_at": ts,
        "updated_by": user,
        "updated_at": ts,
    }
    run_statement(build_update(TBL_SUBMISSIONS, after, {"submission_id": row["submission_id"]}))
    log_change(
        table_name="kri_monthly_submissions",
        record_key=row["submission_id"],
        action="UPDATE",
        changed_by=user,
        before=row.to_dict(),
        after={**row.to_dict(), **after},
    )
    bump_and_rerun(f"{key_prefix}_approve", "Submission approved.", bump=False)


def _reject(row, user: str, reject_notes: str, key_prefix: str) -> None:
    ts = now_utc()
    after = {
        "workflow_status": "Rejected",
        "review_notes": reject_notes.strip(),
        "approved_by": None,
        "approved_at": None,
        "updated_by": user,
        "updated_at": ts,
    }
    run_statement(build_update(TBL_SUBMISSIONS, after, {"submission_id": row["submission_id"]}))
    log_change(
        table_name="kri_monthly_submissions",
        record_key=row["submission_id"],
        action="UPDATE",
        changed_by=user,
        before=row.to_dict(),
        after={**row.to_dict(), **after},
    )
    bump_and_rerun(f"{key_prefix}_reject", "Submission rejected.", bump=False)
