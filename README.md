# KRI Intake — Risk & Compliance Office

A Databricks App that replaces the manual Excel → CSV → upload workflow Risk currently
uses to collect Key Risk Indicators (KRIs) from Maya's departments. Departments submit
their monthly KRI values through a form; Risk manages the KRI definitions and
standardized taxonomy; everything lands directly in Unity Catalog tables ready for
dashboarding.

Source template: `Consolidated KRI File (2026) 1 - Copy.xlsx`, sheet `KRIs`.

## Why two Excel-shaped columns become four tables

The source sheet mixes two different things in one wide table:

1. **KRI attributes** (KRI No., Risk Category, Title, Description, Entity, Frequency,
   Data Owner, Data Source, Green/Amber/Red thresholds, Status, Date Approved) — these
   describe a KRI and rarely change.
2. **Monthly values** — one column pair (value + remarks) added *per month, forever*.
   The sheet already shows the strain: it mixes Jan–Jun 2026 forward columns with
   Jul–Dec 2025 trailing columns, and several risk-category/data-owner values are
   near-duplicates only because of stray whitespace or invisible characters.

Splitting attributes from monthly values (your original `kri_dept_repository` /
`kri_dept_logs` idea) is the right call — that's a standard dimension/fact split and it
is what makes the data dashboardable without ever adding a column again. Two additions
on top of your plan:

- A **lookup table** for the standardized dropdown values, because the raw sheet's
  free-text `risk_category`/`department` columns had ~20+ near-duplicate variants from
  manual entry. Without it, the app just recreates the same drift in a database instead
  of Excel.
- An **audit log**, because this is going to be the system of record for Risk &
  Compliance and Delta tables have no built-in row-level change history usable by
  non-engineers.

## Tables (`dg_dev.sandbox`)

| Table | Renamed from | Purpose |
|---|---|---|
| [`kri_catalog`](sql/002_create_kri_catalog.sql) | `kri_dept_repository` | One row per KRI definition per entity/department: title, description, thresholds, frequency, owner. Reference table. |
| [`kri_monthly_submissions`](sql/003_create_kri_monthly_submissions.sql) | `kri_dept_logs` | One row per KRI per reporting month: actual value, RAG status, remarks, workflow status. Fact table. |
| [`kri_lookup_values`](sql/001_create_kri_lookup_values.sql) | *(new)* | Standardized dropdown values (entity, department, risk category, frequency, unit of measure, statuses) so free-text drift can't recur. Primary key is `(lookup_type, id)`; `id` is auto-assigned per lookup_type and never editable, so `lookup_value` (the display text) can be renamed in place — see **Renaming a lookup value** below. |
| [`kri_audit_log`](sql/004_create_kri_audit_log.sql) | *(new)* | Append-only who/what/when for every write to the two tables above. |

`kri_catalog.kri_id` is an `IDENTITY` surrogate key — it doesn't reuse the source
sheet's manually-assigned `KRI No.` (kept as `legacy_kri_no` for traceability only),
because a sequential number assigned by hand breaks the moment a KRI is added, removed,
or reordered. `kri_monthly_submissions` stores `reporting_period` as a single `DATE`
(first of month) instead of one column per month — this is the change that makes the
table stop growing sideways and start being query/dashboard-friendly.

Run the scripts in `sql/` in numeric order once against your workspace (e.g. via a SQL
warehouse / notebook with `MODIFY` on `dg_dev.sandbox`). `006` only applies if you
already ran the original `001` (which used `sort_order` as a plain display-order column
with `(lookup_type, lookup_value)` as the primary key) — a fresh `001` already creates
the current shape and `006` is a no-op you can skip.

### Threshold format rules (unit-of-measure aware)

Green/Amber/Red threshold validation in `utils/validation.py` depends on the KRI's
`unit_of_measure`:

| Unit | Format | Example |
|---|---|---|
| Percent | number + `%` | `75%`, `>=75%-90%` |
| Ratio | decimal, up to 3 dp, no `%` | `0.753` |
| Days | whole number, no decimal | `60`, `60-65` |
| PHP Amount | decimal, up to 2 dp, no `%` | `1000000.00` |
| Count | whole number, no decimal | `5` |
| Status / Narrative | free text | `On-time` |

Percent form was chosen over decimal form (`0.75`) for Percent-unit thresholds because
it matches how thresholds are already communicated and is unambiguous in isolation
(e.g. in an audit log entry) without cross-referencing the unit dropdown.

For every unit except Status / Narrative, a `-` counts as a range separator only when
it sits between two numbers/operators (e.g. `75%-90%`) — not when it's a leading
negative sign (e.g. `-5%`). When it is a range (or a comparison like `>=75%-90%`), the
left number must be strictly lower than the right one; internal whitespace is stripped
first, so `75% - 90%` validates the same as `75%-90%`.

Monthly Intake's "Actual value" field (`validate_actual_value()`) uses the same
per-unit number formats, but never allows comparison operators or a range: a
submission is one measurement, not a band, so `5%` is valid for a Percent KRI but
`>=75%` or `75%-90%` are rejected. A KRI with no `unit_of_measure` set yet accepts any
text, same as Status / Narrative.
first, so `75% - 90%` validates the same as `75%-90%`.

### Renaming a lookup value

Department (and other lookup) names change over time. Use **Administration → Lookup
Values → Edit a value** rather than deactivating and re-adding — it updates
`lookup_value` in place (keeping the same `id`) and cascades the new text into every
`kri_catalog` / `kri_monthly_submissions` row that already used the old text, via
`utils/db.py`'s `LOOKUP_CASCADE_TARGETS` mapping and `cascade_rename_lookup_value()`.
Both the rename and the cascade are logged to `kri_audit_log`. If a lookup type is ever
added that isn't one of `entity`/`department`/`risk_category`/`frequency`/
`unit_of_measure`/`kri_status`/`workflow_status`/`rag_status`, add it to
`LOOKUP_CASCADE_TARGETS` too or renames of it won't propagate anywhere.

## App structure

```
app.py                      Streamlit entry point / navigation
view_groups.py               Page registry
views/
  kri_monthly_intake.py       Departments submit/edit their monthly KRI value
  kri_dashboard.py            RAG overview + trend per KRI
  kri_catalog_manager.py      Risk defines/edits KRIs, thresholds, status
  kri_lookup_admin.py         Risk manages the standardized dropdown values
utils/
  db.py                        Connection handling + safe SQL literal/MERGE builders
  audit.py                     Writes to kri_audit_log
sql/                          DDL + one-time lookup seed, run in order
scripts/migrate_excel_to_dbx.py  One-time backfill from the existing Excel file
```

All writes go through `utils/db.py`'s `sql_literal()` / `build_insert()` /
`build_update()` / `build_merge_upsert()` helpers, which escape every value (quotes
doubled, per standard SQL literal escaping) instead of interpolating user input
directly into SQL strings.

## Setup

1. **Create the tables** — run `sql/001` through `sql/004` against `dg_dev.sandbox`,
   then `sql/005_seed_kri_lookup_values.sql` to load the standardized taxonomy. `005` is
   a `MERGE`, safe to re-run.
2. **Backfill history (optional)** —
   `python scripts/migrate_excel_to_dbx.py --excel "<path to the xlsx>" --out-dir ./out`
   parses the `KRIs` sheet and writes `kri_catalog_seed.csv` /
   `kri_monthly_submissions_seed.csv` for review. Load the catalog CSV first (Delta
   assigns real `kri_id` values on insert), map the real ids back onto the submissions
   CSV by `(entity, department, kri_title)`, then load submissions — the script's
   `--load` flag explains this and stops short of doing it blindly, since the ids it
   generates locally are only placeholders.
   **Note:** the source sheet has no per-month RAG status, only thresholds as free
   text. Migrated rows default to `rag_status = "Green"` / `workflow_status =
   "Approved"` — treat this as a known gap in the historical backfill, not in the app;
   going forward every submission requires the submitter to pick RAG explicitly.
3. **Deploy as a Databricks App** — attach a SQL warehouse resource named
   `sql-warehouse` (see `app.yaml`) so `DATABRICKS_WAREHOUSE_ID` is populated
   automatically. Grant the app's service principal:
   - `USE CATALOG` on `dg_dev`, `USE SCHEMA` on `dg_dev.sandbox`
   - `SELECT, MODIFY` on all four tables above
   - `CAN USE` on the attached SQL warehouse
4. **Local development** — `pip install -r requirements.txt`, set `DATABRICKS_HOST`
   and either a configured CLI profile or `DATABRICKS_TOKEN`, plus
   `DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/<id>`, then `streamlit run app.py`.

## Status

All four tables exist live in `dg_dev.sandbox` and the app has been deployed and
smoke-tested end to end (KRI Catalog Manager add, Monthly Intake first submit and edit,
Lookup Values add/rename/deactivate). Two bugs turned up during that testing and are
fixed on `main`:
- `DEFAULT` clauses in the original DDL failed against this workspace's Delta feature
  set (`WRONG_COLUMN_DEFAULTS_FOR_DELTA_FEATURE_NOT_ENABLED`) — dropped, since the app
  always sets those columns explicitly on insert anyway.
- Editing an already-submitted month crashed (`NaTType does not support strftime`):
  `sql_literal()` didn't recognize `pandas.NaT` (what a `NULL` timestamp column becomes
  after `fetchall_arrow().to_pandas()`) as a null value. Fixed to check `pd.isna()`.

Still worth independently verifying before wider rollout: RAG-threshold parsing isn't
attempted anywhere (submitters pick RAG manually, by design), and the historical Excel
backfill (see below) hasn't been loaded into the live tables yet.

## Other tables you may want later (not built here)

- **`kri_workflow_comments`** if approval needs threaded back-and-forth beyond the
  single `remarks` field (maker/checker discussion history).
- **A department→entity ownership mapping table** if department names should be
  constrained per entity rather than global (right now any department can be picked
  for any entity).
- **A monthly submission reminder/tracking table** if Risk wants to see who *hasn't*
  submitted yet each month, rather than only what has been submitted.
