from datetime import date

import streamlit as st

from utils.access import require_page_access
from utils.dashboard_metrics import (
    CONSECUTIVE_AMBER_PERIODS,
    CONSECUTIVE_RED_PERIODS,
    departments_with_missing,
    departments_with_persistent_red,
    departments_with_recovery,
    departments_with_trending_amber,
    missing_submissions,
    persistent_red_kris,
    recovery_to_green_kris,
    trending_amber_kris,
)
from utils.db import TBL_CATALOG, TBL_SUBMISSIONS, fetch_lookup, run_query, sql_literal

require_page_access("dashboard")

st.header("KRI Overview", divider=True)
st.write(
    "RCO view of RAG performance across departments. Framework signals highlight "
    "trending Amber, persistent Red, return to Green, and missing submissions."
)

entities = fetch_lookup("entity")
departments = fetch_lookup("department")
today = date.today()
default_period = date(today.year, today.month, 1)

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    entity_filter = st.selectbox("Entity", ["All"] + entities)
with col2:
    department_filter = st.selectbox("Department", ["All"] + departments)
with col3:
    lookback_months = st.selectbox("Lookback window", [3, 6, 12, 24], index=2)
with col4:
    rag_filter = st.selectbox("RAG status", ["All", "Green", "Amber", "Red"])
with col5:
    missing_period = st.date_input(
        "Missing submissions — reporting period",
        value=default_period,
        help="First day of the reporting month/quarter you are closing (e.g. 2026-03-01).",
    )
missing_period_first = date(missing_period.year, missing_period.month, 1)

official_only = st.checkbox(
    "Framework alerts use Approved submissions only",
    value=True,
    help="Signal counters treat only Approved rows as submitted; missing-submission checks use the same rule when checked.",
)

def _catalog_filter_sql(table_prefix: str = "") -> str:
    p = f"{table_prefix}." if table_prefix else ""
    clauses = [f"{p}kri_status = 'Active'"]
    if entity_filter != "All":
        clauses.append(f"{p}entity = {sql_literal(entity_filter)}")
    if department_filter != "All":
        clauses.append(f"{p}department = {sql_literal(department_filter)}")
    return " AND ".join(clauses)


catalog_df = run_query(
    f"""
    SELECT kri_id, entity, department, risk_category, kri_title, frequency
    FROM {TBL_CATALOG}
    WHERE {_catalog_filter_sql()}
    ORDER BY entity, department, kri_title
    """
)

period_submissions_df = run_query(
    f"""
    SELECT s.kri_id, s.reporting_period, s.workflow_status, s.rag_status,
           c.entity, c.department, c.kri_title
    FROM {TBL_SUBMISSIONS} s
    JOIN {TBL_CATALOG} c ON c.kri_id = s.kri_id
    WHERE {_catalog_filter_sql('c')}
      AND s.reporting_period = {sql_literal(missing_period_first)}
    """
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
    SELECT c.kri_id, c.entity, c.department, c.risk_category, c.kri_title, c.unit_of_measure,
           s.reporting_period, s.actual_value_text, s.actual_value_numeric,
           s.rag_status, s.workflow_status, s.remarks
    FROM {TBL_SUBMISSIONS} s
    JOIN {TBL_CATALOG} c ON c.kri_id = s.kri_id
    WHERE {where_sql}
    ORDER BY s.reporting_period DESC
    """
)

alert_df = df[df["workflow_status"] == "Approved"].copy() if official_only and not df.empty else df.copy()

trending_df = trending_amber_kris(alert_df)
persistent_df = persistent_red_kris(alert_df)
recovery_df = recovery_to_green_kris(alert_df)
missing_df = missing_submissions(catalog_df, period_submissions_df, official_only=official_only)

st.subheader("RCO framework signals", divider="gray")
st.caption(
    f"**Trending Amber / Persistent Red:** **{CONSECUTIVE_AMBER_PERIODS} consecutive "
    f"reporting periods** for the same KRI, all Amber or all Red. **Return to Green:** "
    f"latest period Green, prior period Amber or Red. **Missing submissions:** active "
    f"KRIs with no submission for **{missing_period_first}**."
)

r1c1, r1c2, r1c3, r1c4 = st.columns(4)
r1c1.metric("Departments — trending Amber", departments_with_trending_amber(trending_df))
r1c2.metric("KRIs — trending Amber", len(trending_df))
r1c3.metric("Departments — return to Green", departments_with_recovery(recovery_df))
r1c4.metric("KRIs — return to Green", len(recovery_df))

r2c1, r2c2, r2c3, r2c4 = st.columns(4)
r2c1.metric("Departments — persistent Red", departments_with_persistent_red(persistent_df))
r2c2.metric("KRIs — persistent Red", len(persistent_df))
r2c3.metric("Departments — missing submission", departments_with_missing(missing_df))
r2c4.metric("KRIs — missing submission", len(missing_df))

exp1, exp2 = st.columns(2)
with exp1:
    with st.expander("Trending Amber & persistent Red", expanded=False):
        if trending_df.empty and persistent_df.empty:
            st.write("None in the lookback window.")
        else:
            if not trending_df.empty:
                st.markdown("**Trending Amber**")
                st.dataframe(
                    trending_df.sort_values(["department", "kri_title"]),
                    use_container_width=True,
                    hide_index=True,
                )
            if not persistent_df.empty:
                st.markdown("**Persistent Red**")
                st.dataframe(
                    persistent_df.sort_values(["department", "kri_title"]),
                    use_container_width=True,
                    hide_index=True,
                )
with exp2:
    with st.expander("Return to Green & missing submissions", expanded=not missing_df.empty):
        if not recovery_df.empty:
            st.markdown("**Return to Green**")
            st.dataframe(
                recovery_df.sort_values(["department", "kri_title"]),
                use_container_width=True,
                hide_index=True,
            )
        elif missing_df.empty:
            st.write("No return-to-Green KRIs in the lookback window.")
        if not missing_df.empty:
            st.markdown(f"**Missing for {missing_period_first}**")
            st.dataframe(
                missing_df[
                    ["entity", "department", "risk_category", "kri_title", "frequency"]
                ].sort_values(["department", "kri_title"]),
                use_container_width=True,
                hide_index=True,
            )

if df.empty:
    st.info("No submissions in the lookback window for the table and trend charts below.")
else:
    latest = df.sort_values("reporting_period").groupby(["entity", "department", "kri_title"]).tail(1)

    st.subheader("Latest RAG snapshot", divider="gray")
    c1, c2, c3 = st.columns(3)
    c1.metric("🟢 Green (latest)", int((latest["rag_status"] == "Green").sum()))
    c2.metric("🟠 Amber (latest)", int((latest["rag_status"] == "Amber").sum()))
    c3.metric("🔴 Red (latest)", int((latest["rag_status"] == "Red").sum()))

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
