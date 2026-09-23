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

## Not in scope (unless RCO revisits)

- Frequency-aware calendar grids (e.g. inferring “missing quarter” when no row exists).
- Requiring N consecutive Greens after a breach to clear trending Amber retroactively.
