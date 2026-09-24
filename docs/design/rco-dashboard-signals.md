# RCO dashboard — framework signals (confirmed)

**Status:** RCO-confirmed  
**Implementation:** `views/kri_dashboard.py`, `utils/dashboard_metrics.py`

## Trending Amber

- **Rule:** A KRI is in **trending Amber** when its **last 3 consecutive reporting periods** (by `reporting_period`, per KRI) all have `rag_status = Amber`.
- **Scope:** Evaluated **per KRI** (entity + department + title), then rolled up to department counts on the dashboard.
- **Frequency:** Monthly, quarterly, annual, and other cadences use the **same “3 periods” rule** — three consecutive **submitted reporting periods for that KRI**, not three calendar months regardless of frequency.
- **Data:** By default, only `workflow_status = Approved` rows count toward alerts (toggle on the dashboard).

## Return to Green

- **Rule:** A KRI **returned to Green** when its **latest** reporting period in the filtered window is `Green` and the **immediately prior** period for that same KRI was `Amber` or `Red`.
- **Scope:** Per KRI; department metric = distinct departments with at least one such KRI.

## Persistent Red

- **Rule:** Same as Trending Amber, but the last **3 consecutive reporting periods** for the KRI are all **Red**.
- **Scope / frequency / Approved-only:** Same conventions as Trending Amber.

## Missing submissions

- **Rule:** An **Active** catalog KRI (after entity/department filters) has **no** submission row for the **selected reporting period** (first day of month chosen on the dashboard, e.g. `2026-03-01`).
- **Data:** Respects the **Approved-only** toggle when checked (Submitted-only rows do not count as submitted). Rejected rows never count.
- **Note:** RCO picks the period to close (monthly close vs quarter-end month for quarterly KRIs). The app does not auto-infer quarter-end dates from `frequency` yet.

## Not in scope (unless RCO revisits)

- Frequency-aware calendar grids (e.g. auto-due dates from `frequency` without a period picker).
- Requiring N consecutive Greens after a breach to clear trending Amber retroactively.
