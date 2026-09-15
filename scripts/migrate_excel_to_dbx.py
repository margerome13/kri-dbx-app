"""One-time backfill: transform the wide "Consolidated KRI File" -> "KRIs" sheet into
the normalized kri_catalog / kri_monthly_submissions shape.

By default this only writes two CSVs to --out-dir for review before loading. Pass
--load to also write directly into Databricks (requires DATABRICKS_HOST, a
credentials_provider resolvable by databricks.sdk.core.Config -- e.g. a configured
CLI profile or DATABRICKS_TOKEN -- and DATABRICKS_HTTP_PATH env vars).

Known limitation: the source sheet does not record a Green/Amber/Red status per
month, only the numbers/text and the three threshold definitions (which are free-text
and not reliably machine-parseable, e.g. "<=16.00%", ">16.01%-24%\\n", "On-time"). RAG
status for migrated historical rows is defaulted to "Green" and workflow_status to
"Approved" -- review and correct via the app's dashboard/intake pages if precise
historical RAG matters. Going forward, the intake form asks the submitter to select
RAG status explicitly so this gap does not recur.

Usage:
    python scripts/migrate_excel_to_dbx.py --excel "/path/to/Consolidated KRI File (2026) 1 - Copy.xlsx" --out-dir ./out
    python scripts/migrate_excel_to_dbx.py --excel "..." --out-dir ./out --load
"""
import argparse
import re
import uuid
from datetime import date, datetime, timezone
from typing import Optional

import openpyxl
import pandas as pd

HEADER_ROW = 2
FIRST_DATA_ROW = 3

ATTR_COLUMNS = {
    1: "legacy_kri_no",
    2: "risk_category",
    3: "kri_title",
    4: "description",
    5: "entity",
    6: "frequency",
    7: "department",       # sheet header: "KRI Data Owner"
    8: "data_source",      # sheet header: "KRI Data Source"
    9: "kri_status",
    10: "date_approved",
    11: "threshold_green",
    12: "threshold_amber",
    13: "threshold_red",
}


def clean_text(value) -> Optional[str]:
    if value is None:
        return None
    text = str(value).replace("​", "").strip()
    return text or None


def parse_numeric(value) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"-?\d+(\.\d+)?", str(value).replace(",", ""))
    return float(match.group()) if match else None


def load_month_column_groups(ws) -> list[dict]:
    """Group consecutive month columns with the remarks column that follows them."""
    groups = []
    current_months: list[tuple[int, date]] = []
    max_col = ws.max_column
    for col in range(14, max_col + 1):
        header = ws.cell(row=HEADER_ROW, column=col).value
        if isinstance(header, datetime):
            current_months.append((col, date(header.year, header.month, 1)))
        else:
            if current_months:
                groups.append({"months": current_months, "remarks_col": col})
                current_months = []
    if current_months:
        groups.append({"months": current_months, "remarks_col": None})
    return groups


def transform(excel_path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    wb = openpyxl.load_workbook(excel_path, data_only=True)
    ws = wb["KRIs"]
    month_groups = load_month_column_groups(ws)

    catalog_rows = []
    submission_rows = []
    kri_key_to_id = {}
    next_kri_id = 1

    for row in range(FIRST_DATA_ROW, ws.max_row + 1):
        if ws.cell(row=row, column=1).value is None:
            continue

        attrs = {name: ws.cell(row=row, column=col).value for col, name in ATTR_COLUMNS.items()}
        entity = clean_text(attrs["entity"])
        department = clean_text(attrs["department"])
        kri_title = clean_text(attrs["kri_title"])
        if not (entity and department and kri_title):
            continue

        key = (entity, department, kri_title)
        if key not in kri_key_to_id:
            kri_id = next_kri_id
            next_kri_id += 1
            kri_key_to_id[key] = kri_id
            catalog_rows.append(
                {
                    "kri_id": kri_id,
                    "entity": entity,
                    "department": department,
                    "risk_category": clean_text(attrs["risk_category"]),
                    "kri_title": kri_title,
                    "description": clean_text(attrs["description"]),
                    "unit_of_measure": None,
                    "frequency": clean_text(attrs["frequency"]) or "Monthly",
                    "data_source": clean_text(attrs["data_source"]),
                    "threshold_green": clean_text(attrs["threshold_green"]),
                    "threshold_amber": clean_text(attrs["threshold_amber"]),
                    "threshold_red": clean_text(attrs["threshold_red"]),
                    "kri_status": clean_text(attrs["kri_status"]) or "Active",
                    "date_approved": attrs["date_approved"].date()
                    if isinstance(attrs["date_approved"], datetime)
                    else None,
                    "legacy_kri_no": attrs["legacy_kri_no"],
                    "created_by": "migration_script",
                    "created_at": datetime.now(timezone.utc),
                    "updated_by": None,
                    "updated_at": None,
                }
            )
        kri_id = kri_key_to_id[key]

        for group in month_groups:
            remarks = clean_text(ws.cell(row=row, column=group["remarks_col"]).value) if group["remarks_col"] else None
            for col, period in group["months"]:
                raw_value = ws.cell(row=row, column=col).value
                if raw_value is None or str(raw_value).strip() == "":
                    continue
                submission_rows.append(
                    {
                        "submission_id": str(uuid.uuid4()),
                        "kri_id": kri_id,
                        "reporting_period": period,
                        "actual_value_text": clean_text(raw_value),
                        "actual_value_numeric": parse_numeric(raw_value),
                        "rag_status": "Green",  # see module docstring: not derivable from source
                        "remarks": remarks,
                        "workflow_status": "Approved",
                        "submitted_by": "migration_script",
                        "submitted_at": datetime.now(timezone.utc),
                        "approved_by": None,
                        "approved_at": None,
                        "updated_by": None,
                        "updated_at": None,
                    }
                )

    return pd.DataFrame(catalog_rows), pd.DataFrame(submission_rows)


def load_to_databricks(catalog_df: pd.DataFrame, submissions_df: pd.DataFrame) -> None:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from utils.db import TBL_CATALOG, TBL_SUBMISSIONS, build_insert, run_statement

    for _, row in catalog_df.drop(columns=["kri_id"]).iterrows():
        run_statement(build_insert(TBL_CATALOG, row.to_dict()))

    catalog_lookup = catalog_df.set_index("kri_id")
    for _, row in submissions_df.iterrows():
        row_dict = row.to_dict()
        # kri_id in submissions_df is the temporary in-script id; real load needs the
        # kri_id assigned by IDENTITY on insert into kri_catalog. Re-map by natural key
        # via a follow-up SELECT if loading directly -- left as a manual step because
        # it depends on IDENTITY values only Databricks assigns at insert time.
        run_statement(build_insert(TBL_SUBMISSIONS, row_dict))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--excel", required=True)
    parser.add_argument("--out-dir", default="./out")
    parser.add_argument("--load", action="store_true", help="Also load directly into Databricks")
    args = parser.parse_args()

    from pathlib import Path

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    catalog_df, submissions_df = transform(args.excel)
    catalog_df.to_csv(out_dir / "kri_catalog_seed.csv", index=False)
    submissions_df.to_csv(out_dir / "kri_monthly_submissions_seed.csv", index=False)

    print(f"KRI catalog rows: {len(catalog_df)}")
    print(f"Monthly submission rows: {len(submissions_df)}")
    print(f"Written to {out_dir.resolve()}")
    print(
        "NOTE: rag_status for every migrated row defaults to 'Green' -- the source "
        "file does not record RAG per month. Review/correct before treating this as "
        "history, or re-run intake for periods where the correct RAG matters."
    )

    if args.load:
        print(
            "Direct --load is provided as a starting point only: kri_catalog.kri_id is "
            "an IDENTITY column, so the ids used here are placeholders. Load kri_catalog "
            "first, SELECT the real ids back by (entity, department, kri_title), remap "
            "kri_id in submissions_df, then load kri_monthly_submissions. Recommended "
            "path is to review the CSVs and load them with a Databricks COPY INTO / "
            "notebook instead."
        )
