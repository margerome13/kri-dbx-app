# Entity and department model

## Two layers (do not confuse them)

| Layer | Table | Purpose |
|--------|--------|---------|
| **Taxonomy** | `kri_lookup_values` (`lookup_type = department`) | Standard department **names** (e.g. Data Governance, id 25). Used in Add a KRI, User Role Manager, dashboard filters. |
| **Operational** | `kri_catalog` | Each KRI is tied to **`entity` + `department`** (plus title, thresholds, etc.). Submit KRI loads **KRIs** from here for the chosen entity and department. |

Adding a department in **Lookup Values** alone does **not** create KRIs. RCO must **Add a KRI** for each `(entity, department)` combination that should report.

## Why Submit KRI did not show “Data Governance”

Previously, the department dropdown on Submit KRI (for Admins) listed only departments that already had **Active** rows in `kri_catalog` for the selected **entity**. A new lookup value with no catalog rows never appeared.

**Now:** Admins pick department from **Lookup Values**; the KRI list still comes from the catalog. If there are no Active KRIs for that entity + department, the page says so and points to **Add a KRI**.

**Makers** still see a fixed department from **User Role Manager** (not the full lookup list).

## Entity × department

- **Entity** (Maya PH, Maya Bank, One Maya) and **department** are independent dropdowns in **Add a KRI**, both from lookup taxonomies.
- The same department **name** can be used under more than one entity (separate catalog rows per entity).
- There is **no** lookup row per `(entity, department)` pair today — only a global department list.

### Implications

| Area | Behavior |
|------|----------|
| **Add a KRI** | Any lookup department × any lookup entity. |
| **Submit KRI** | Entity + department select which **catalog** KRIs load. |
| **User Role Manager** | One **department** string per Maker/Checker (no entity). A Maker with “Data Governance” may submit for that department under **whichever entity** has Active KRIs — they choose entity on the form. |
| **Dashboard / review filters** | Filter by entity and/or department string; same global department names. |

### If RCO needs stricter rules later

Examples: “Data Governance exists only under Maya PH” or “this Maker is PH-only”:

- Add an **entity–department allowlist** table, or
- Scope `kri_user_roles` with **entity** (and optionally split one person into two rows per entity — currently one role per email).

Until then, keep naming consistent in Lookup Values and define KRIs explicitly per entity in the catalog.
