"""RCO dashboard aggregations over submission history (pandas in, counts/lists out).

RCO-confirmed rules (see docs/design/rco-dashboard-signals.md):
- Trending Amber / Persistent Red: last 3 consecutive reporting periods per KRI are
  all Amber or all Red (same rule for all catalog frequencies).
- Return to Green: latest period Green, prior period Amber or Red.
- Missing submissions: active catalog KRIs with no submission for the selected period.
"""
from __future__ import annotations

import pandas as pd

CONSECUTIVE_AMBER_PERIODS = 3
CONSECUTIVE_RED_PERIODS = 3


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


def persistent_red_kris(df: pd.DataFrame) -> pd.DataFrame:
    return kris_with_trailing_rag(
        df, periods=CONSECUTIVE_RED_PERIODS, rag="Red"
    )


def departments_with_signal(signal_df: pd.DataFrame) -> int:
    if signal_df.empty:
        return 0
    return int(signal_df["department"].nunique())


def departments_with_trending_amber(trending_df: pd.DataFrame) -> int:
    return departments_with_signal(trending_df)


def departments_with_persistent_red(persistent_df: pd.DataFrame) -> int:
    return departments_with_signal(persistent_df)


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
    return departments_with_signal(recovery_df)


def missing_submissions(
    catalog_df: pd.DataFrame,
    period_submissions_df: pd.DataFrame,
    *,
    official_only: bool,
) -> pd.DataFrame:
    """Active catalog KRIs with no row for the selected reporting period."""
    if catalog_df.empty:
        return pd.DataFrame()

    if period_submissions_df.empty:
        submitted_ids: set = set()
    elif official_only:
        submitted_ids = set(
            period_submissions_df.loc[
                period_submissions_df["workflow_status"] == "Approved", "kri_id"
            ].astype(int)
        )
    else:
        submitted_ids = set(
            period_submissions_df.loc[
                period_submissions_df["workflow_status"] != "Rejected", "kri_id"
            ].astype(int)
        )

    missing = catalog_df[~catalog_df["kri_id"].astype(int).isin(submitted_ids)].copy()
    return missing


def departments_with_missing(missing_df: pd.DataFrame) -> int:
    return departments_with_signal(missing_df)
