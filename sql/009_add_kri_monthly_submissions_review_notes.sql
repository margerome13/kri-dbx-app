-- Maker-checker design: Checker reject/approve notes (see docs/design/maker-checker-department-scope.md).
-- Required on Reject; optional on Approve. Enforced in the app, not in DDL.
ALTER TABLE dg_dev.sandbox.kri_monthly_submissions
ADD COLUMN IF NOT EXISTS review_notes STRING
COMMENT 'Checker note: required when workflow_status is Rejected; optional on Approve.';
