# Maker–checker monthly submissions & department-scoped roles

**Status:** RCO-approved (walkthrough follow-up)  
**Audience:** Engineering + Risk & Compliance Office (RCO)  
**App:** Maya KRI (Databricks App, `dg_dev.sandbox`)

This document is the **target design** for the next implementation phase. The deployed app today still uses the **current** behavior described in [README.md](../../README.md) (no submission approval queue, no department filter on roles, CHECKER still has Manage Existing KRIs).

---

## RCO decisions (confirmed)

| Topic | Decision |
|--------|----------|
| Departments vs roles | A department may have **many Makers** (different emails). **One role per person** — not Maker for Finance and Checker for Ops at the same time. |
| One department per person | **OK for now** — single `department` on the user’s one `kri_user_roles` row. Multi-department / multi-role-per-person is **out of scope** until a real case appears. |
| Monthly submissions | **Maker–checker flow** is required. |
| Checker duties | **Approve** or **Reject with reason** only — **never** edit the Maker’s actual value or remarks. |
| Checker catalog access | **Remove** Manage Existing KRIs from CHECKER. Catalog changes stay **Admin-only** (RCO / Risk enter definitions; no in-app catalog maker–checker). |
| Approved corrections | After Checker approval, **only ADMIN** may correct a submission. Makers and Checkers see Approved rows as **read-only**. |

---

## 1. Monthly submission workflow

### 1.1 States

Reuse existing `workflow_status` lookup values (`sql/005_seed_kri_lookup_values.sql`): **Submitted**, **Approved**, **Rejected**. No new lookup values.

`Draft` remains in the lookup table for compatibility but is **not used** in this flow (Makers save as **Submitted**).

```
                    ┌─────────────┐
         create     │  Submitted  │◄──── Maker edit after reject
         or edit ──►│  (in queue) │
                    └──────┬──────┘
                           │
              Checker      │
              Approve      │      Reject (+ review_notes required)
                    ▼      ▼
             ┌──────────┐  ┌──────────┐
             │ Approved │  │ Rejected │
             └──────────┘  └────┬─────┘
                  │            │
                  │            └── Maker may edit value/remarks
                  │                → workflow_status back to Submitted
                  │
                  └── Locked for Maker & Checker; ADMIN may override
```

| State | Maker | Checker | Admin |
|--------|--------|---------|--------|
| *(no row)* | Create → **Submitted** | — | Full access |
| **Submitted** | Edit value/remarks → stays **Submitted** | Approve / Reject | Full access |
| **Rejected** | Edit → reset to **Submitted**; reject reason visible | — (not in queue) | Full access |
| **Approved** | Read-only | Read-only | May edit / correct |

### 1.2 Schema change: `review_notes`

Add one column on `kri_monthly_submissions`:

| Column | Type | Rules |
|--------|------|--------|
| `review_notes` | `STRING` | **Required** when Checker sets `workflow_status = Rejected`. **Optional** on Approve. |

Migration: `sql/009_add_kri_monthly_submissions_review_notes.sql`.

Existing columns used as follows:

| Column | Usage in this design |
|--------|----------------------|
| `remarks` | Maker-only narrative (unchanged; still required in practice for Amber/Red). |
| `approved_by`, `approved_at` | Set **only on Approve** (Checker or Admin acting as reviewer). |
| `updated_by`, `updated_at` | Set on every write; on **Reject**, captures who rejected and when (no separate `rejected_by`). |
| `submitted_by`, `submitted_at` | Set on first submit; optionally refreshed when Maker re-submits after reject (implementation choice: update `submitted_at` on resubmit from Rejected → Submitted). |

### 1.3 Two pages (segregation of duties)

**Monthly Intake** (MAKER + ADMIN)

- Same overall UX as today (entity → department → KRI → month → actual value → RAG → save).
- **Department scope:** only the signed-in user’s assigned department (see §2). ADMIN sees all departments (today’s behavior).
- **Edit rules:** writable only when status is **Rejected** or there is no row yet, or status is **Submitted** *(Maker may still fix before Checker acts)* — once **Approved**, Maker sees **read-only** (values + status + any `review_notes` from a prior reject if applicable).
- Saving sets `workflow_status = Submitted` (insert or update from Rejected/Submitted).

**Review Submissions** (CHECKER + ADMIN) — **new page**

- Queue: `workflow_status = Submitted`, joined to `kri_catalog` for titles/thresholds context.
- **Department scope:** CHECKER sees only submissions where `kri_catalog.department` = their `kri_user_roles.department`. ADMIN sees all.
- Per row: read-only display of Maker’s `actual_value_text`, `rag_status`, `remarks`; actions **Approve** / **Reject**.
- Reject: require `review_notes`; set `workflow_status = Rejected`; set `updated_by` / `updated_at`.
- Approve: optional `review_notes`; set `workflow_status = Approved`; set `approved_by` / `approved_at`; set `updated_by` / `updated_at`.
- **No** fields to edit Maker data on this page.

---

## 2. Department-scoped roles

### 2.1 Terminology

Restricting Makers/Checkers to their department’s rows is **department-scoped RBAC** (row-level access by department). Audit/compliance wording: **data segregation by department**.

### 2.2 Schema change: `kri_user_roles.department`

Add nullable `department STRING` to `kri_user_roles`.

Migration: `sql/010_add_kri_user_roles_department.sql`.

| Role | `department` | Data visibility |
|------|----------------|-----------------|
| **ADMIN** | `NULL` (blank in UI) | All departments |
| **MAKER** | **Required** — must match a value in `kri_lookup_values` (`lookup_type = department`) | `kri_catalog` / `kri_monthly_submissions` filtered to that department |
| **CHECKER** | **Required** | Same filter on Review Submissions (and any read-only views) |

**Primary key unchanged:** one row per `user_email`. Multiple Makers per department = multiple rows with the same `department` and `role = MAKER`.

**Department moves:** edit the user’s row in **User Role Manager** (same as changing role today).

**Validation (app):**

- On upsert: if role is MAKER or CHECKER, `department` is required and must be an active lookup value.
- If role is ADMIN, force `department` to `NULL`.

### 2.3 Filtering rules (implementation)

Centralize in a small helper (e.g. `utils/department_scope.py`):

- `user_department(email) -> str | None`
- `catalog_department_clause(alias)` / `submission_department_clause(alias)` for SQL `WHERE` fragments

Apply on:

- Monthly Intake (department dropdown pre-selected / locked for MAKER; CHECKER does not use this page).
- Review Submissions queue.
- Dashboard (optional phase: ADMIN-only today; if opened to CHECKER later, filter consistently).

**Do not** rely on the client alone — every write path must verify the submission’s KRI belongs to the user’s department (or user is ADMIN).

---

## 3. Role → page matrix (target)

| Page | ADMIN | MAKER | CHECKER |
|------|:-----:|:-----:|:-------:|
| Monthly Intake | ✓ (all depts) | ✓ (own dept) | — |
| **Review Submissions** | ✓ (all depts) | — | ✓ (own dept) |
| KRI Overview (Dashboard) | ✓ | — | — *(unchanged unless RCO asks)* |
| Add a KRI | ✓ | — | — |
| Manage Existing KRIs | ✓ | — | — |
| Lookup Values | ✓ | — | — |
| User Role Manager | ✓ | — | — |

Update `config/user_roles.py` `ROLE_PAGES` and `view_groups.py` `PAGE_REGISTRY` when implementing.

---

## 4. Databricks App access (unchanged)

In-app roles do **not** replace Databricks **Share → Can Use**. Onboarding remains:

1. Workspace: grant app access via Databricks App **Share**.
2. App: add user in **User Role Manager** with role + department (for MAKER/CHECKER).

---

## 5. Implementation checklist

Use this as the engineering backlog (not yet done on `main` unless explicitly shipped):

- [ ] Run `sql/009` and `sql/010` in `dg_dev.sandbox`.
- [ ] Extend User Role Manager: department field + validation.
- [ ] Implement department scope helper + enforce on reads/writes.
- [ ] Monthly Intake: workflow locks + resubmit from Rejected → Submitted.
- [ ] New view `views/kri_review_submissions.py` + navigation entry.
- [ ] Trim CHECKER from `catalog_manage` in `ROLE_PAGES`.
- [ ] Audit log: include `review_notes` and workflow transitions in `kri_audit_log` payloads.
- [ ] Update [user guide](../index.html) / README **Roles** section when behavior ships.
- [ ] Smoke tests: Maker submit → Checker approve; Maker submit → reject → Maker fix → approve; Approved locked for Maker; Admin correction on Approved.

---

## 6. Explicitly deferred

- Multi-department or multi-role rows per `(user_email, department)`.
- In-app maker–checker on **KRI catalog** definitions.
- Reopen workflow (Checker/Maker undo Approve) — corrections are **Admin-only** for now.
- Threaded discussion table (`kri_workflow_comments`) — single `review_notes` per decision is enough for v1.
