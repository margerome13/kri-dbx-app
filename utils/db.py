"""Shared Databricks SQL connection and query helpers for the KRI app.

Every table access goes through this module so that:
- the SQL warehouse connection is resolved and cached in one place, and
- writes are built with sql_literal()/build_insert()/build_update() instead of
  raw f-string interpolation of user input, to avoid SQL injection.
"""
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd
import streamlit as st
from databricks import sql
from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config

CATALOG = "dg_dev"
SCHEMA = "sandbox"

TBL_LOOKUP = f"{CATALOG}.{SCHEMA}.kri_lookup_values"
TBL_CATALOG = f"{CATALOG}.{SCHEMA}.kri_catalog"
TBL_SUBMISSIONS = f"{CATALOG}.{SCHEMA}.kri_monthly_submissions"
TBL_AUDIT = f"{CATALOG}.{SCHEMA}.kri_audit_log"


def new_id() -> str:
    return str(uuid.uuid4())


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def sql_literal(value: Any) -> str:
    """Render a Python value as a safe SQL literal (NULL / number / quoted string)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, datetime):
        return f"TIMESTAMP'{value.strftime('%Y-%m-%d %H:%M:%S')}'"
    text = str(value).replace("'", "''")
    return f"'{text}'"


def build_insert(table: str, row: dict) -> str:
    columns = ", ".join(row.keys())
    values = ", ".join(sql_literal(v) for v in row.values())
    return f"INSERT INTO {table} ({columns}) VALUES ({values})"


def build_merge_upsert(table: str, row: dict, key_columns: list[str]) -> str:
    """MERGE-based upsert keyed on key_columns; all other columns in `row` are set on match."""
    on_clause = " AND ".join(f"t.{k} = {sql_literal(row[k])}" for k in key_columns)
    set_clause = ", ".join(
        f"{k} = {sql_literal(v)}" for k, v in row.items() if k not in key_columns
    )
    columns = ", ".join(row.keys())
    values = ", ".join(sql_literal(v) for v in row.values())
    return (
        f"MERGE INTO {table} AS t USING (SELECT 1) AS s ON {on_clause} "
        f"WHEN MATCHED THEN UPDATE SET {set_clause} "
        f"WHEN NOT MATCHED THEN INSERT ({columns}) VALUES ({values})"
    )


def build_update(table: str, set_values: dict, where: dict) -> str:
    set_clause = ", ".join(f"{k} = {sql_literal(v)}" for k, v in set_values.items())
    where_clause = " AND ".join(f"{k} = {sql_literal(v)}" for k, v in where.items())
    return f"UPDATE {table} SET {set_clause} WHERE {where_clause}"


def build_delete(table: str, where: dict) -> str:
    where_clause = " AND ".join(f"{k} = {sql_literal(v)}" for k, v in where.items())
    return f"DELETE FROM {table} WHERE {where_clause}"


@st.cache_resource(ttl="1h")
def get_connection():
    cfg = Config()
    http_path = _resolve_http_path(cfg)
    return sql.connect(
        server_hostname=cfg.host,
        http_path=http_path,
        credentials_provider=lambda: cfg.authenticate,
    )


def _resolve_http_path(cfg: Config) -> str:
    """Resolve the SQL warehouse HTTP path.

    Preferred: DATABRICKS_WAREHOUSE_ID, populated automatically when a SQL warehouse
    resource is attached to this Databricks App. Falls back to DATABRICKS_HTTP_PATH
    for local development.
    """
    warehouse_id = os.environ.get("DATABRICKS_WAREHOUSE_ID")
    if warehouse_id:
        w = WorkspaceClient(config=cfg)
        return w.warehouses.get(warehouse_id).odbc_params.path

    http_path = os.environ.get("DATABRICKS_HTTP_PATH")
    if http_path:
        return http_path

    raise RuntimeError(
        "No SQL warehouse configured. Set DATABRICKS_WAREHOUSE_ID (attach a SQL "
        "warehouse resource to this app) or DATABRICKS_HTTP_PATH for local runs."
    )


def current_user_email() -> str:
    """Best-effort identity of the signed-in app user, falling back to the run-as identity."""
    header_email = st.context.headers.get("X-Forwarded-Email") if hasattr(st, "context") else None
    if header_email:
        return header_email
    try:
        w = WorkspaceClient()
        return w.current_user.me().user_name
    except Exception:
        return "unknown"


def run_query(query: str) -> pd.DataFrame:
    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute(query)
        return cursor.fetchall_arrow().to_pandas()


def run_statement(statement: str) -> None:
    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute(statement)


def fetch_lookup(lookup_type: str, active_only: bool = True) -> list[str]:
    where = f"lookup_type = {sql_literal(lookup_type)}"
    if active_only:
        where += " AND is_active = TRUE"
    df = run_query(
        f"SELECT lookup_value FROM {TBL_LOOKUP} WHERE {where} ORDER BY sort_order, lookup_value"
    )
    return df["lookup_value"].tolist() if not df.empty else []
