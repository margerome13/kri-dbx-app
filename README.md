# Maya KRI — Risk & Compliance Office

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
| [`kri_audit_log`](sql/004_create_kri_audit_log.sql) | *(new)* | Append-only who/what/when for every write to every other table below. |
| [`kri_user_roles`](sql/007_create_kri_user_roles.sql) | *(new)* | Who has which app role (ADMIN/MAKER/CHECKER) -- see **Roles** below. Managed entirely via Administration → User Role Manager. |

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
the current shape and `006` is a no-op you can skip. `008` seeds `kri_user_roles` with
the users originally hardcoded in `config/user_roles.py`; safe to re-run. When shipping
the RCO maker–checker design, also run `009` (`review_notes` on submissions) and `010`
(`department` on user roles) — see [docs/design/maker-checker-department-scope.md](docs/design/maker-checker-department-scope.md).

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
| Duration (H:MM:SS) | elapsed time `H:MM:SS` (minutes/seconds 00–59); stored/compared as total seconds | `1:30:00`, `0:00:00-0:30:00`, `>=1:00:00` |
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

Beyond each threshold's own format, two more checks run on top of the catalog's
Green/Amber/Red thresholds (both skipped for Status / Narrative KRIs, same as above):

- **Sequential, non-overlapping thresholds** (`validate_rag_threshold_sequence()`,
  enforced in Add a KRI and Manage Existing KRIs, blocks saving) — Green, Amber, and
  Red must form one strictly monotonic band with no overlaps: either increasing
  (`Green < Amber < Red`, e.g. Green `1-3`, Amber `4-6`, Red `7-10`) or decreasing
  (`Red < Amber < Green`). Only checked once all three thresholds are individually
  valid and non-blank (in Manage Existing KRIs, clearing any one of them skips this
  check rather than blocking the save).
- **Threshold gap warning** (`find_rag_threshold_gap()`, same two pages, non-blocking)
  — flags when two adjacent bands leave a numeric gap wide enough to contain a value
  that would match neither, e.g. Amber `3-4` next to Red `46` for a Count KRI leaves
  `5`-`45` uncovered. Shown as a warning alongside the success message, not an error —
  a gap might be deliberate (that range's policy genuinely isn't decided yet), so it's
  surfaced for a human to double check rather than enforced. A unit's own smallest
  possible step doesn't count as a gap (e.g. Days/Count `2` next to `3`), see
  `GAP_TOLERANCE`.

### RAG status is computed, not chosen

Monthly Intake doesn't let the submitter pick a RAG status — `resolve_rag_status()`
derives it from the Actual value against the KRI's own Green/Amber/Red thresholds and
shows it read-only, so an Actual value and RAG status can never disagree. A value
inside one band's own typed numbers is a direct match; a value that falls in a gap
between bands (like `44` in the `1-3` / `4-6` / `46` gap-warning example above)
resolves to whichever of Green/Red sits on that side of Amber — on the assumption
that a KRI only gets worse (or only gets better) the further a value goes past the
defined range in one direction, so `44` there reads Red even though it doesn't hit
Red's own typed `46`.

The manual RAG radio only reappears as a fallback when nothing numeric can be
compared: a Status / Narrative KRI, no `unit_of_measure` set, or a catalog with one of
Green/Amber/Red left blank or unparseable. Fixing the underlying catalog data (see the
gap warning above) is preferable to relying on this fallback.

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
app.py                      Streamlit entry point / navigation, shows the role badge
view_groups.py               Role-aware page registry (PAGE_REGISTRY + get_groups_for_user)
config/
  user_roles.py               Role resolution logic + BOOTSTRAP_ADMINS + which pages each role sees
views/
  kri_monthly_intake.py       Everyone: submit/edit your monthly KRI value
  kri_dashboard.py            Admin only: RAG overview + trend per KRI
  kri_catalog_add.py          Admin only: define new KRIs, thresholds, frequency
  kri_catalog_manage.py       Admin + Checker: review/update existing KRIs
  kri_lookup_admin.py         Admin only: manage the standardized dropdown values
  user_role_admin.py          Admin only: add/change/remove who has which role
  access_denied.py            Shown instead of any page to an unlisted user
utils/
  db.py                        Connection handling + safe SQL literal/MERGE builders
  access.py                    require_page_access() -- per-page role guard
  audit.py                     Writes to kri_audit_log
sql/                          DDL + one-time lookup seed, run in order
scripts/migrate_excel_to_dbx.py  One-time backfill from the existing Excel file
```

All writes go through `utils/db.py`'s `sql_literal()` / `build_insert()` /
`build_update()` / `build_merge_upsert()` helpers, which escape every value (quotes
doubled, per standard SQL literal escaping) instead of interpolating user input
directly into SQL strings.

## Roles

| Role | Sees | Data scope |
|---|---|---|
| ADMIN | Submit KRI, Review Submitted KRIs, KRI Overview, Add a KRI, Manage Existing KRIs, Lookup Values, User Role Manager | All departments |
| MAKER | Submit KRI only | Assigned **department** only (`kri_user_roles.department`) |
| CHECKER | Review Submitted KRIs only (approve / reject with reason) | Assigned **department** only |
| *(unlisted)* | Access Denied | — |

MAKER/CHECKER rows must include a department in **User Role Manager**. Approved monthly submissions are read-only for Makers; corrections after approval are **Admin-only**. Design notes: [docs/design/maker-checker-department-scope.md](docs/design/maker-checker-department-scope.md).

Role membership lives in `dg_dev.sandbox.kri_user_roles` — managed entirely in-app via
**Administration → User Role Manager** (Admin only): add a user with a role, change
someone's role, or remove one, no code change or redeploy needed. Every write there
is logged to `kri_audit_log` just like every other table.

**`config/user_roles.py`'s `BOOTSTRAP_ADMINS`** is the one thing that still lives in
code: a short hardcoded list that is always ADMIN regardless of what's in the
`kri_user_roles` table, so a misconfigured, emptied, or query-failing roles table can
never lock every admin out — there's always at least one way back in. Keep this list
as short as possible (today: just `mar.abana@paymaya.com`). The User Role Manager page
also blocks removing or demoting the *last* ADMIN row in the table (a softer,
day-to-day safeguard on top of `BOOTSTRAP_ADMINS`, so admin work doesn't always have
to fall back to the bootstrap account).

Enforcement is two layers: `view_groups.get_groups_for_user()` only lists pages a
role is allowed to see, so the sidebar itself never shows a Maker "Manage Existing
KRIs" or "Lookup Values"; every restricted page also calls
`utils/access.require_page_access()` at the top as a second, direct check — defense
in depth against someone bookmarking a page URL their role shouldn't reach.
Monthly Intake has no guard since every role can see it.

The current signed-in user and their resolved role are shown at the top of every
page (`app.py`), styled the same way as the
[Merchant Business Size and Gender Review App](https://github.com/margerome13/dbx-merchant-biz-size-gender-app).

This app doesn't cache any data query (every page re-reads fresh on every rerun), so
role lookups aren't an exception either — a role change in User Role Manager applies
on the affected user's very next click, with no cache to clear or TTL to wait out.

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
   - `SELECT, MODIFY` on all five tables above
   - `CAN USE` on the attached SQL warehouse
   Role-based access (see **Roles** above) depends on `utils/db.py`'s
   `current_user_email()` correctly reading the signed-in user's email from the
   Databricks Apps proxy headers (`X-Forwarded-Preferred-Username` /
   `X-Forwarded-Email`) or the SDK's `current_user.me()` -- if the role badge shown
   at the top of the app doesn't match who's actually logged in, that's the first
   place to check.
4. **Local development** — `pip install -r requirements.txt`, set `DATABRICKS_HOST`
   and either a configured CLI profile or `DATABRICKS_TOKEN`, plus
   `DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/<id>`, then `streamlit run app.py`.

## Status

All five tables exist live in `dg_dev.sandbox` and the app has been deployed and
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

## Product design (RCO)

- **[Maker–checker monthly submissions & department-scoped roles](docs/design/maker-checker-department-scope.md)** — approved workflow, schema deltas (`009`/`010`), page split (Monthly Intake vs Review Submissions), and implementation checklist. App code on `main` may still reflect the pre-maker–checker behavior until that checklist is completed.
- **[RCO dashboard framework signals](docs/design/rco-dashboard-signals.md)** — Trending Amber, persistent Red (3 consecutive periods per KRI), Return to Green, and missing submissions for a selected reporting period.

## Other tables you may want later (not built here)

- **`kri_workflow_comments`** if approval needs threaded back-and-forth beyond
  `review_notes` (v1 uses a single Checker note per approve/reject).
- **A department→entity ownership mapping table** if department names should be
  constrained per entity rather than global (right now any department can be picked
  for any entity).
- **A monthly submission reminder/tracking table** if Risk wants to see who *hasn't*
  submitted yet each month, rather than only what has been submitted.
