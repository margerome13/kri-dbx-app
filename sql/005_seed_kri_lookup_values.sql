-- Idempotent seed/refresh of kri_lookup_values with a cleaned taxonomy derived from the
-- "Consolidated KRI File (2026)" -> "KRIs" sheet. The raw sheet had many near-duplicate
-- free-text values (trailing spaces, invisible unicode characters, e.g. "Compliance Risk"
-- vs "Compliance Risk​") which this list de-duplicates. Safe to re-run: existing
-- values are left untouched, only new canonical values are inserted.
MERGE INTO dg_dev.sandbox.kri_lookup_values AS target
USING (
    SELECT * FROM VALUES
        -- entity
        ('entity', 'Maya PH', 1),
        ('entity', 'Maya Bank', 2),
        ('entity', 'One Maya', 3),

        -- frequency
        ('frequency', 'Daily', 1),
        ('frequency', 'Monthly', 2),
        ('frequency', 'Quarterly', 3),
        ('frequency', 'Annually', 4),

        -- kri_status (lifecycle of a KRI definition in kri_catalog)
        ('kri_status', 'Active', 1),
        ('kri_status', 'Inactive', 2),
        ('kri_status', 'Retired', 3),

        -- workflow_status (lifecycle of a monthly submission)
        ('workflow_status', 'Draft', 1),
        ('workflow_status', 'Submitted', 2),
        ('workflow_status', 'Approved', 3),
        ('workflow_status', 'Rejected', 4),

        -- rag_status
        ('rag_status', 'Green', 1),
        ('rag_status', 'Amber', 2),
        ('rag_status', 'Red', 3),

        -- unit_of_measure
        ('unit_of_measure', 'Percent', 1),
        ('unit_of_measure', 'Count', 2),
        ('unit_of_measure', 'Days', 3),
        ('unit_of_measure', 'PHP Amount', 4),
        ('unit_of_measure', 'Ratio', 5),
        ('unit_of_measure', 'Status / Narrative', 6),

        -- risk_category, cleaned from the KRIs sheet
        ('risk_category', 'People Risk', 1),
        ('risk_category', 'Process Risk', 2),
        ('risk_category', 'Process / Compliance Risk', 3),
        ('risk_category', 'Compliance', 4),
        ('risk_category', 'Compliance Risk', 5),
        ('risk_category', 'Audit / Compliance', 6),
        ('risk_category', 'Financial Risk', 7),
        ('risk_category', 'Market & Pricing Risk', 8),
        ('risk_category', 'Fraud Risk', 9),
        ('risk_category', 'Operational / AML', 10),
        ('risk_category', 'Reputational Risk', 11),
        ('risk_category', 'Strategic Risk', 12),
        ('risk_category', 'Change Management', 13),
        ('risk_category', 'Capacity Management', 14),
        ('risk_category', 'Obsolescence', 15),
        ('risk_category', 'InfoSec', 16),
        ('risk_category', 'Identity and Access Management', 17),
        ('risk_category', 'Endpoint Protection', 18),
        ('risk_category', 'Vulnerability Management', 19),
        ('risk_category', 'Incident Management', 20),
        ('risk_category', 'End User Security Awareness', 21),

        -- department ("KRI Data Owner" in the source sheet), cleaned
        ('department', 'People Group', 1),
        ('department', 'Operational Risk', 2),
        ('department', 'Customer Service', 3),
        ('department', 'Customer Support', 4),
        ('department', 'Finance', 5),
        ('department', 'Deposit', 6),
        ('department', 'Loan Channeling', 7),
        ('department', 'Credit Card', 8),
        ('department', 'Consumer Wallet', 9),
        ('department', 'MSME Business', 10),
        ('department', 'VASP/Crypto', 11),
        ('department', 'Marketing - PAC', 12),
        ('department', 'Business Development - Payments (Enterprise Growth)', 13),
        ('department', 'Procurement', 14),
        ('department', 'AML Investigation', 15),
        ('department', 'Antifraud - Acquiring', 16),
        ('department', 'Bank Compliance', 17),
        ('department', 'RCO - Regulatory Compliance', 18),
        ('department', 'Internal Audit', 19),
        ('department', 'InfoSec', 20),
        ('department', 'InfoSec - DPO', 21),
        ('department', 'Tech Ops', 22)
    AS s(lookup_type, lookup_value, id)
) AS source
ON target.lookup_type = source.lookup_type AND target.lookup_value = source.lookup_value
WHEN NOT MATCHED THEN INSERT (lookup_type, lookup_value, id, is_active, created_by, created_at)
VALUES (source.lookup_type, source.lookup_value, source.id, TRUE, current_user(), current_timestamp());
