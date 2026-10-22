-- Adds "Deadline Date" to unit_of_measure lookup -- a signed whole number of days
-- relative to a deadline (negative = before, 0 = on, positive = after). Same number
-- format as Days under the hood; this is its own unit purely so the hint text and
-- display read correctly for "early/late vs. a due date" KRIs (e.g. regulatory report
-- submission timeliness) instead of looking like a plain duration count.
-- Safe to re-run (MERGE).
MERGE INTO dg_dev.sandbox.kri_lookup_values AS target
USING (
    SELECT * FROM VALUES
        ('unit_of_measure', 'Deadline Date', 8)
    AS s(lookup_type, lookup_value, id)
) AS source
ON target.lookup_type = source.lookup_type AND target.lookup_value = source.lookup_value
WHEN NOT MATCHED THEN INSERT (lookup_type, lookup_value, id, is_active, created_by, created_at)
VALUES (source.lookup_type, source.lookup_value, source.id, TRUE, current_user(), current_timestamp());
