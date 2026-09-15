-- KRI catalog: one row per Key Risk Indicator definition, per entity + department.
-- This replaces the "attribute" columns (KRI No., Risk Category, KRI Title, Description,
-- Entity, Frequency, Data Owner, Data Source, Green/Amber/Red thresholds, Status, Date
-- Approved) from the left-hand side of the Consolidated KRI File "KRIs" sheet.
--
-- Renamed from the working name "kri_dept_repository" -> kri_catalog, to match common
-- data-governance terminology (a "metric catalog") and to avoid implying the table is
-- scoped/partitioned by department (it holds every department's KRIs).
CREATE TABLE IF NOT EXISTS dg_dev.sandbox.kri_catalog (
    kri_id            BIGINT GENERATED ALWAYS AS IDENTITY COMMENT 'Surrogate key, auto-generated. Stable even if a KRI is renamed.',
    entity            STRING NOT NULL COMMENT 'Legal entity / business unit, e.g. Maya PH, Maya Bank, One Maya. See kri_lookup_values(entity).',
    department        STRING NOT NULL COMMENT 'Owning department / KRI Data Owner. See kri_lookup_values(department).',
    risk_category     STRING NOT NULL COMMENT 'Standardized risk taxonomy. See kri_lookup_values(risk_category).',
    kri_title         STRING NOT NULL COMMENT 'Short name of the indicator, e.g. Employee Turnover.',
    description       STRING COMMENT 'Definition and calculation formula for the KRI.',
    unit_of_measure    STRING COMMENT 'How the actual value is expressed, e.g. percent, days, count, PHP, status_text. See kri_lookup_values(unit_of_measure).',
    frequency         STRING NOT NULL COMMENT 'Monitoring cadence: Monthly, Quarterly, Annually, Daily. See kri_lookup_values(frequency).',
    data_source       STRING COMMENT 'Source of the reported value as recorded in the original template -- often a named point-of-contact rather than a system name.',
    threshold_green   STRING COMMENT 'Green (within appetite) threshold definition, kept as free text since thresholds are often ranges/prose.',
    threshold_amber   STRING COMMENT 'Amber (watch) threshold definition.',
    threshold_red     STRING COMMENT 'Red (breach) threshold definition.',
    kri_status        STRING NOT NULL DEFAULT 'Active' COMMENT 'Active, Inactive, or Retired. See kri_lookup_values(kri_status).',
    date_approved     DATE COMMENT 'Date the KRI definition/thresholds were approved by Risk.',
    legacy_kri_no     INT COMMENT 'Original "KRI No." from the source Excel template, kept for migration traceability only.',
    created_by        STRING NOT NULL,
    created_at        TIMESTAMP NOT NULL,
    updated_by        STRING,
    updated_at        TIMESTAMP,
    CONSTRAINT kri_catalog_pk PRIMARY KEY (kri_id)
)
USING DELTA
COMMENT 'Reference table: catalog of KRI definitions (one row per KRI per entity/department). Written to by the KRI Catalog Manager page.'
TBLPROPERTIES (delta.enableChangeDataFeed = true);
