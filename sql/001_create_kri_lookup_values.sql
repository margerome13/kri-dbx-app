-- Standardized taxonomy values used to populate dropdowns in the KRI app and to
-- keep entity / department / risk category / frequency spellings consistent across
-- submitting departments (the source Excel had many near-duplicate free-text values,
-- e.g. "Compliance Risk" vs "Compliance Risk " vs "Process / Compliance Risk").
--
-- `id` is assigned by the app as "next in sequence within this lookup_type" (not a
-- global counter) and is never user-editable -- it exists so a value's display text
-- (`lookup_value`) can be renamed later (e.g. a department is renamed) without
-- changing the row's identity. Column mapping is enabled so `id` could be renamed
-- again in the future without a table rebuild.
CREATE TABLE IF NOT EXISTS dg_dev.sandbox.kri_lookup_values (
    lookup_type   STRING NOT NULL COMMENT 'Category of value: entity, department, risk_category, frequency, unit_of_measure, kri_status, workflow_status, rag_status',
    id            INT NOT NULL COMMENT 'Assigned by the app: next in sequence within this lookup_type. Not user-editable.',
    lookup_value  STRING NOT NULL COMMENT 'Canonical display value shown in the app. Editable -- renaming cascades into every table that stores this text directly, see utils/db.py LOOKUP_CASCADE_TARGETS.',
    is_active     BOOLEAN NOT NULL COMMENT 'Inactive values are hidden from new entries but kept for historical records. Always set explicitly by the app.',
    created_by    STRING NOT NULL,
    created_at    TIMESTAMP NOT NULL,
    CONSTRAINT kri_lookup_values_pk PRIMARY KEY (lookup_type, id)
)
USING DELTA
COMMENT 'Reference/dimension table: standardized dropdown values for the KRI intake app.'
TBLPROPERTIES (
    delta.enableChangeDataFeed = true,
    'delta.columnMapping.mode' = 'name',
    'delta.minReaderVersion' = '2',
    'delta.minWriterVersion' = '5'
);
