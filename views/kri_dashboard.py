import pandas as pd
import streamlit as st

from utils.access import require_page_access
from utils.dashboard_metrics import (
    CONSECUTIVE_AMBER_PERIODS,
    departments_with_recovery,
    departments_with_trending_amber,
    recovery_to_green_kris,
    trending_amber_kris,
)
from utils.db import TBL_CATALOG, TBL_SUBMISSIONS, fetch_lookup, run_query, sql_literal

require_page_access("dashboard")

st.header("KRI Overview", divider=True)
st.write(
    "RCO view of RAG performance across departments. Use filters to narrow the window; "
    "framework alerts below highlight **trending Amber** and **return to Green**."
)

entities = fetch_lookup("entity")
departments = fetch_lookup("department")

col1, col2, col3, col4 = st.columns(4)
with col1:
    entity_filter = st.selectbox("Entity", ["All"] + entities)
with col2:
    department_filter = st.selectbox("Department", ["All"] + departments)
with col3:
    lookback_months = st.selectbox("Lookback window", [3, 6, 12, 24], index=2)
with col4:
    rag_filter = st.selectbox("RAG status", ["All", "Green", "Amber", "Red"])

official_only = st.checkbox(
    "Framework alerts use Approved submissions only",
    value=True,
    help="Trending Amber and Return to Green counters ignore Submitted/Rejected rows when checked.",
)

where_clauses = [
    f"s.reporting_period >= add_months(current_date(), -{int(lookback_months)})",
    "s.workflow_status != 'Rejected'",
]
if entity_filter != "All":
    where_clauses.append(f"c.entity = {sql_literal(entity_filter)}")
if department_filter != "All":
    where_clauses.append(f"c.department = {sql_literal(department_filter)}")
if rag_filter != "All":
    where_clauses.append(f"s.rag_status = {sql_literal(rag_filter)}")
where_sql = " AND ".join(where_clauses)

df = run_query(
    f"""
    SELECT c.entity, c.department, c.risk_category, c.kri_title, c.unit_of_measure,
           s.reporting_period, s.actual_value_text, s.actual_value_numeric,
           s.rag_status, s.workflow_status, s.remarks
    FROM {TBL_SUBMISSIONS} s
    JOIN {TBL_CATALOG} c ON c.kri_id = s.kri_id
    WHERE {where_sql}
    ORDER BY s.reporting_period DESC
    """
)

if df.empty:
    st.info("No submissions found for the selected filters.")
    st.stop()

alert_df = df[df["workflow_status"] == "Approved"] if official_only else df.copy()

trending_df = trending_amber_kris(alert_df)
recovery_df = recovery_to_green_kris(alert_df)
dept_trending = departments_with_trending_amber(trending_df)
dept_recovery = departments_with_recovery(recovery_df)

st.subheader("RCO framework signals", divider="gray")
st.caption(
    f"**Trending Amber:** a KRI with **{CONSECUTIVE_AMBER_PERIODS} consecutive** "
    f"Amber periods (most recent periods in the lookback window). "
    "**Return to Green:** latest period is Green and the prior period was Amber or Red."
)

m1, m2, m3, m4 = st.columns(4)
m1.metric(
    "Departments — trending Amber",
    dept_trending,
    help=f"Distinct departments with at least one KRI at {CONSECUTIVE_AMBER_PERIODS}+ consecutive Ambers.",
)
m2.metric(
    "KRIs — trending Amber",
    len(trending_df),
)
m3.metric(
    "Departments — return to Green",
    dept_recovery,
    help="Distinct departments with at least one KRI that moved from Amber/Red to Green.",
)
m4.metric(
    "KRIs — return to Green",
    len(recovery_df),
)

detail1, detail2 = st.columns(2)
with detail1:
    with st.expander("KRIs in trending Amber", expanded=not trending_df.empty):
        if trending_df.empty:
            st.write("None in this filter window.")
        else:
            st.dataframe(
                trending_df.sort_values(["department", "kri_title"]),
                use_container_width=True,
                hide_index=True,
            )
with detail2:
    with st.expander("KRIs returned to Green", expanded=False):
        if recovery_df.empty:
            st.write("None in this filter window.")
        else:
            st.dataframe(
                recovery_df.sort_values(["department", "kri_title"]),
                use_container_width=True,
                hide_index=True,
            )

latest = df.sort_values("reporting_period").groupby(["entity", "department", "kri_title"]).tail(1)

st.subheader("Latest RAG snapshot", divider="gray")
col1, col2, col3 = st.columns(3)
col1.metric("🟢 Green (latest)", int((latest["rag_status"] == "Green").sum()))
col2.metric("🟠 Amber (latest)", int((latest["rag_status"] == "Amber").sum()))
col3.metric("🔴 Red (latest)", int((latest["rag_status"] == "Red").sum()))

st.dataframe(
    latest[
        [
            "entity",
            "department",
            "risk_category",
            "kri_title",
            "reporting_period",
            "actual_value_text",
            "rag_status",
            "workflow_status",
        ]
    ].sort_values(["entity", "department", "kri_title"]),
    use_container_width=True,
    hide_index=True,
)

st.subheader("Trend for a specific KRI")
kri_options = sorted(df["kri_title"].unique().tolist())
selected_kri = st.selectbox("KRI", kri_options)
trend_df = df[df["kri_title"] == selected_kri].sort_values("reporting_period")

if trend_df["actual_value_numeric"].notna().any():
    chart_df = trend_df.set_index("reporting_period")[["actual_value_numeric"]]
    st.line_chart(chart_df)
else:
    st.write("This KRI reports a narrative/status value rather than a number:")
    st.dataframe(
        trend_df[["reporting_period", "actual_value_text", "rag_status", "workflow_status"]],
        use_container_width=True,
        hide_index=True,
    )

with st.expander("Remarks for Amber/Red periods"):
    remarks_df = trend_df[trend_df["rag_status"].isin(["Amber", "Red"])][
        ["reporting_period", "rag_status", "remarks"]
    ]
    if remarks_df.empty:
        st.write("No Amber/Red periods in the selected window.")
    else:
        st.dataframe(remarks_df, use_container_width=True, hide_index=True)
