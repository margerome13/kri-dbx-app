-- Append-only change history for kri_catalog and kri_monthly_submissions. Delta tables
-- have no triggers, so every write in the app also inserts one row here (see
-- utils/audit.py) -- this gives Risk & Compliance a full "who changed what, when" trail
-- for governance/audit purposes without needing Delta table history/time travel queries.
CREATE TABLE IF NOT EXISTS dg_dev.sandbox.kri_audit_log (
    audit_id      STRING NOT NULL COMMENT 'Surrogate key (UUID).',
    table_name    STRING NOT NULL COMMENT 'kri_catalog or kri_monthly_submissions.',
    record_key    STRING NOT NULL COMMENT 'kri_id or submission_id of the affected row, as text.',
    action        STRING NOT NULL COMMENT 'INSERT, UPDATE, or DELETE.',
    changed_by    STRING NOT NULL,
    changed_at    TIMESTAMP NOT NULL,
    before_value  STRING COMMENT 'JSON snapshot of the row before the change. NULL for INSERT.',
    after_value   STRING COMMENT 'JSON snapshot of the row after the change. NULL for DELETE.',
    CONSTRAINT kri_audit_log_pk PRIMARY KEY (audit_id)
)
USING DELTA
COMMENT 'Audit table: append-only change history for KRI catalog and submission writes made through the app.';
