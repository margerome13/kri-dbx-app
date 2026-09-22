-- Maker-checker design: Checker reject/approve notes (see docs/design/maker-checker-department-scope.md).
-- Required on Reject; optional on Approve. Enforced in the app, not in DDL.
-- Safe to re-run only if the column does not exist yet (Delta has no IF NOT EXISTS here).
ALTER TABLE dg_dev.sandbox.kri_monthly_submissions
ADD COLUMN review_notes STRING
COMMENT 'Checker note: required when workflow_status is Rejected; optional on Approve.';
