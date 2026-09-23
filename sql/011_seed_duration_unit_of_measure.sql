-- Adds Duration (H:MM:SS) to unit_of_measure lookup. Safe to re-run (MERGE).
MERGE INTO dg_dev.sandbox.kri_lookup_values AS target
USING (
    SELECT * FROM VALUES
        ('unit_of_measure', 'Duration (H:MM:SS)', 7)
    AS s(lookup_type, lookup_value, id)
) AS source
ON target.lookup_type = source.lookup_type AND target.lookup_value = source.lookup_value
WHEN NOT MATCHED THEN INSERT (lookup_type, lookup_value, id, is_active, created_by, created_at)
VALUES (source.lookup_type, source.lookup_value, source.id, TRUE, current_user(), current_timestamp());
