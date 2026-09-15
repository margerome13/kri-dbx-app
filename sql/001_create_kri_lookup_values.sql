-- Standardized taxonomy values used to populate dropdowns in the KRI app and to
-- keep entity / department / risk category / frequency spellings consistent across
-- submitting departments (the source Excel had many near-duplicate free-text values,
-- e.g. "Compliance Risk" vs "Compliance Risk " vs "Process / Compliance Risk").
CREATE TABLE IF NOT EXISTS dg_dev.sandbox.kri_lookup_values (
    lookup_type   STRING NOT NULL COMMENT 'Category of value: entity, department, risk_category, frequency, unit_of_measure, kri_status, workflow_status, rag_status',
    lookup_value  STRING NOT NULL COMMENT 'Canonical display value shown in the app',
    sort_order    INT COMMENT 'Display order within a lookup_type, ascending',
    is_active     BOOLEAN NOT NULL COMMENT 'Inactive values are hidden from new entries but kept for historical records. Always set explicitly by the app.',
    created_by    STRING NOT NULL,
    created_at    TIMESTAMP NOT NULL,
    CONSTRAINT kri_lookup_values_pk PRIMARY KEY (lookup_type, lookup_value)
)
USING DELTA
COMMENT 'Reference/dimension table: standardized dropdown values for the KRI intake app.'
TBLPROPERTIES (delta.enableChangeDataFeed = true);
