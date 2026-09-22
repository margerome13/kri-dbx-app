-- Department-scoped MAKER/CHECKER rows (see docs/design/maker-checker-department-scope.md).
-- NULL department = ADMIN (global visibility). App requires non-null department for MAKER/CHECKER.
ALTER TABLE dg_dev.sandbox.kri_user_roles
ADD COLUMN IF NOT EXISTS department STRING
COMMENT 'Department scope for MAKER/CHECKER (matches kri_lookup_values department). NULL for ADMIN.';
