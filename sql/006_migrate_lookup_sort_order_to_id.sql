-- Migration for a workspace that already ran the original 001 (sort_order-based PK).
-- Skip this if you are creating kri_lookup_values fresh from the current 001 --
-- it already has `id` as part of the primary key.
--
-- Renames sort_order -> id and makes it (together with lookup_type) the primary key,
-- so a value's display text can be renamed without changing the row's identity.
-- Applied against dg_dev.sandbox on 2026-09-15.
ALTER TABLE dg_dev.sandbox.kri_lookup_values SET TBLPROPERTIES (
    'delta.columnMapping.mode' = 'name',
    'delta.minReaderVersion' = '2',
    'delta.minWriterVersion' = '5'
);

ALTER TABLE dg_dev.sandbox.kri_lookup_values RENAME COLUMN sort_order TO id;

ALTER TABLE dg_dev.sandbox.kri_lookup_values ALTER COLUMN id SET NOT NULL;

ALTER TABLE dg_dev.sandbox.kri_lookup_values DROP CONSTRAINT kri_lookup_values_pk;

ALTER TABLE dg_dev.sandbox.kri_lookup_values ADD CONSTRAINT kri_lookup_values_pk PRIMARY KEY (lookup_type, id);
