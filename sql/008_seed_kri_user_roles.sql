-- One-time migration of the users previously hardcoded in config/user_roles.py
-- into the database-backed role table. Safe to re-run: existing rows are left
-- untouched, only missing ones are inserted.
--
-- mar.abana@paymaya.com was listed as both ADMIN and CHECKER in the old hardcoded
-- lists; that already resolved to plain ADMIN (checked first, and a superset of
-- CHECKER's access anyway), so it gets a single ADMIN row here for the same result.
-- mar.abana@paymaya.com is also a BOOTSTRAP_ADMINS entry in code, so this row is
-- redundant-but-consistent -- it just makes them visible in the User Role Manager
-- table like everyone else, rather than being an invisible exception.
MERGE INTO dg_dev.sandbox.kri_user_roles AS target
USING (
    SELECT * FROM VALUES
        ('mar.abana@paymaya.com', 'ADMIN'),
        ('revylen.asilo@paymaya.com', 'ADMIN'),
        ('gilbert.lavides@paymaya.com', 'MAKER')
    AS s(user_email, role)
) AS source
ON target.user_email = source.user_email
WHEN NOT MATCHED THEN INSERT (user_email, role, assigned_by, assigned_at)
VALUES (source.user_email, source.role, current_user(), current_timestamp());
