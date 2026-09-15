import pandas as pd
import streamlit as st

from utils.db import TBL_CATALOG, TBL_SUBMISSIONS, fetch_lookup, run_query, sql_literal

st.header("KRI Overview", divider=True)
st.write("RAG status across all submitted KRIs. Use the filters below to narrow the view.")

entities = fetch_lookup("entity")
col1, col2, col3 = st.columns(3)
with col1:
    entity_filter = st.selectbox("Entity", ["All"] + entities)
with col2:
    lookback_months = st.selectbox("Lookback window", [3, 6, 12, 24], index=2)
with col3:
    rag_filter = st.selectbox("RAG status", ["All", "Green", "Amber", "Red"])

where_clauses = [f"s.reporting_period >= add_months(current_date(), -{int(lookback_months)})"]
if entity_filter != "All":
    where_clauses.append(f"c.entity = {sql_literal(entity_filter)}")
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

latest = df.sort_values("reporting_period").groupby(["entity", "department", "kri_title"]).tail(1)

col1, col2, col3 = st.columns(3)
col1.metric("🟢 Green (latest)", int((latest["rag_status"] == "Green").sum()))
col2.metric("🟠 Amber (latest)", int((latest["rag_status"] == "Amber").sum()))
col3.metric("🔴 Red (latest)", int((latest["rag_status"] == "Red").sum()))

st.subheader("Latest status by KRI")
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
        trend_df[["reporting_period", "actual_value_text", "rag_status"]],
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
