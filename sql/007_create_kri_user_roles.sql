-- Who has which app role, managed in-app via Administration -> User Role Manager
-- once this table exists (no code change or redeploy needed to add/change/remove a
-- user's role). One row per user -- an admin who's also listed elsewhere simply gets
-- the single row 'ADMIN', since Admin's page set is already a superset of every
-- other role's.
--
-- config/user_roles.py's BOOTSTRAP_ADMINS is the one thing NOT in this table: a
-- small hardcoded list that is always ADMIN regardless of what's in here, so this
-- table can never be emptied, corrupted, or misconfigured into locking every admin
-- out. The User Role Manager page also blocks removing/demoting the last ADMIN row
-- in this table (a softer safeguard on top of BOOTSTRAP_ADMINS).
CREATE TABLE IF NOT EXISTS dg_dev.sandbox.kri_user_roles (
    user_email   STRING NOT NULL COMMENT 'Signed-in user email; matched case-insensitively by the app.',
    role         STRING NOT NULL COMMENT 'ADMIN, MAKER, or CHECKER.',
    assigned_by  STRING NOT NULL,
    assigned_at  TIMESTAMP NOT NULL,
    updated_by   STRING,
    updated_at   TIMESTAMP,
    CONSTRAINT kri_user_roles_pk PRIMARY KEY (user_email)
)
USING DELTA
COMMENT 'Reference table: who has which KRI Intake app role. Managed via Administration -> User Role Manager.'
TBLPROPERTIES (delta.enableChangeDataFeed = true);
