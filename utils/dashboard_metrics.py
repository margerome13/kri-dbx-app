"""RCO dashboard aggregations over submission history (pandas in, counts/lists out).

RCO-confirmed rules (see docs/design/rco-dashboard-signals.md):
- Trending Amber: last 3 consecutive reporting periods per KRI are all Amber (same
  rule for monthly, quarterly, etc. — three periods on that KRI's timeline).
- Return to Green: latest period Green, prior period Amber or Red.
"""
from __future__ import annotations

import pandas as pd

CONSECUTIVE_AMBER_PERIODS = 3


def _kri_key(df: pd.DataFrame) -> pd.DataFrame:
    return df.assign(
        _kri_key=df["entity"].astype(str)
        + "|"
        + df["department"].astype(str)
        + "|"
        + df["kri_title"].astype(str)
    )


def kris_with_trailing_rag(
    df: pd.DataFrame,
    *,
    periods: int,
    rag: str,
) -> pd.DataFrame:
    """KRIs whose last `periods` submissions (by reporting_period) are all `rag`."""
    if df.empty or periods < 1:
        return pd.DataFrame()

    keyed = _kri_key(df)
    rows = []
    for _key, grp in keyed.groupby("_kri_key", sort=False):
        ordered = grp.sort_values("reporting_period")
        if len(ordered) < periods:
            continue
        tail = ordered.tail(periods)
        if (tail["rag_status"] == rag).all():
            last = ordered.iloc[-1]
            rows.append(
                {
                    "entity": last["entity"],
                    "department": last["department"],
                    "kri_title": last["kri_title"],
                    "risk_category": last.get("risk_category"),
                    "latest_period": last["reporting_period"],
                    "latest_rag": last["rag_status"],
                }
            )
    return pd.DataFrame(rows)


def trending_amber_kris(df: pd.DataFrame) -> pd.DataFrame:
    return kris_with_trailing_rag(
        df, periods=CONSECUTIVE_AMBER_PERIODS, rag="Amber"
    )


def departments_with_trending_amber(trending_df: pd.DataFrame) -> int:
    if trending_df.empty:
        return 0
    return int(trending_df["department"].nunique())


def recovery_to_green_kris(df: pd.DataFrame) -> pd.DataFrame:
    """KRIs whose latest period is Green and the immediately prior period was Amber or Red."""
    if df.empty:
        return pd.DataFrame()

    keyed = _kri_key(df)
    rows = []
    for _key, grp in keyed.groupby("_kri_key", sort=False):
        ordered = grp.sort_values("reporting_period")
        if len(ordered) < 2:
            continue
        prev, last = ordered.iloc[-2], ordered.iloc[-1]
        if last["rag_status"] == "Green" and prev["rag_status"] in ("Amber", "Red"):
            rows.append(
                {
                    "entity": last["entity"],
                    "department": last["department"],
                    "kri_title": last["kri_title"],
                    "risk_category": last.get("risk_category"),
                    "previous_period": prev["reporting_period"],
                    "previous_rag": prev["rag_status"],
                    "latest_period": last["reporting_period"],
                    "latest_rag": last["rag_status"],
                }
            )
    return pd.DataFrame(rows)


def departments_with_recovery(recovery_df: pd.DataFrame) -> int:
    if recovery_df.empty:
        return 0
    return int(recovery_df["department"].nunique())
