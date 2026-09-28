/* ============================================================================
   01_load_structured.sql — RAW load, CURATED conform, data quality gates
============================================================================ */
USE ROLE CARELENS_ADMIN; USE WAREHOUSE CARELENS_WH; USE DATABASE CARELENS; USE SCHEMA RAW;

CREATE OR REPLACE TABLE RAW_PATIENTS (
  patient_id STRING, member_id STRING, first_name STRING, last_name STRING,
  birth_date DATE, sex STRING, city STRING, state STRING, postal_code STRING,
  primary_language STRING, pcp_npi STRING, deceased_flag NUMBER, data_source STRING);

CREATE OR REPLACE TABLE RAW_MEMBERS (
  member_id STRING, patient_id STRING, payer_name STRING, plan_id STRING,
  line_of_business STRING, enroll_start DATE, enroll_end DATE,
  risk_program STRING, attributed_clinic STRING);

CREATE OR REPLACE TABLE RAW_ENCOUNTERS (
  encounter_id STRING, patient_id STRING, encounter_type STRING,
  start_date DATE, end_date DATE, length_of_stay_days NUMBER,
  admission_source STRING, discharge_disposition STRING, facility STRING, readmit_30d NUMBER);

CREATE OR REPLACE TABLE RAW_CLAIMS (
  claim_id STRING, encounter_id STRING, member_id STRING, patient_id STRING,
  claim_type STRING, service_date DATE, billed_amount NUMBER(18,2),
  allowed_amount NUMBER(18,2), paid_amount NUMBER(18,2), member_liability NUMBER(18,2),
  claim_status STRING, denial_reason STRING, drg_code STRING);

CREATE OR REPLACE TABLE RAW_DIAGNOSES (
  patient_id STRING, icd10_code STRING, diagnosis_description STRING, onset_date DATE,
  charlson_weight NUMBER, hcc_flag NUMBER, clinical_status STRING);

CREATE OR REPLACE TABLE RAW_MEDICATIONS (
  patient_id STRING, rx_id STRING, medication_name STRING, drug_class STRING,
  start_date DATE, days_supply NUMBER, refills NUMBER,
  adherence_pdc NUMBER(4,2), active_flag NUMBER);

CREATE OR REPLACE TABLE RAW_LABS (
  patient_id STRING, loinc_code STRING, test_name STRING, unit STRING,
  result_value NUMBER(18,3), ref_low NUMBER(18,3), ref_high NUMBER(18,3),
  abnormal_flag NUMBER, collected_date DATE);

CREATE OR REPLACE TABLE RAW_ED_VISITS (
  patient_id STRING, ed_visit_date DATE, chief_complaint STRING, admitted_flag NUMBER);

COPY INTO RAW_PATIENTS    FROM @STRUCTURED_STAGE/patients.csv    FILE_FORMAT = (FORMAT_NAME = CSV_HEADER) ON_ERROR = ABORT_STATEMENT;
COPY INTO RAW_MEMBERS     FROM @STRUCTURED_STAGE/members.csv     FILE_FORMAT = (FORMAT_NAME = CSV_HEADER) ON_ERROR = ABORT_STATEMENT;
COPY INTO RAW_ENCOUNTERS  FROM @STRUCTURED_STAGE/encounters.csv  FILE_FORMAT = (FORMAT_NAME = CSV_HEADER) ON_ERROR = ABORT_STATEMENT;
COPY INTO RAW_CLAIMS      FROM @STRUCTURED_STAGE/claims.csv      FILE_FORMAT = (FORMAT_NAME = CSV_HEADER) ON_ERROR = ABORT_STATEMENT;
COPY INTO RAW_DIAGNOSES   FROM @STRUCTURED_STAGE/diagnoses.csv   FILE_FORMAT = (FORMAT_NAME = CSV_HEADER) ON_ERROR = ABORT_STATEMENT;
COPY INTO RAW_MEDICATIONS FROM @STRUCTURED_STAGE/medications.csv FILE_FORMAT = (FORMAT_NAME = CSV_HEADER) ON_ERROR = ABORT_STATEMENT;
COPY INTO RAW_LABS        FROM @STRUCTURED_STAGE/labs.csv        FILE_FORMAT = (FORMAT_NAME = CSV_HEADER) ON_ERROR = ABORT_STATEMENT;
COPY INTO RAW_ED_VISITS   FROM @STRUCTURED_STAGE/ed_visits.csv   FILE_FORMAT = (FORMAT_NAME = CSV_HEADER) ON_ERROR = ABORT_STATEMENT;

USE SCHEMA CURATED;

CREATE OR REPLACE TABLE DIM_PATIENT AS
SELECT p.patient_id, p.member_id, p.first_name, p.last_name,
       INITCAP(p.first_name || ' ' || p.last_name) AS full_name,
       p.birth_date, DATEDIFF('year', p.birth_date, CURRENT_DATE) AS age_years,
       p.sex, p.city, p.state, p.postal_code, p.primary_language, p.pcp_npi,
       m.payer_name, m.plan_id, m.line_of_business, m.risk_program, m.attributed_clinic,
       m.enroll_start, p.data_source
FROM RAW.RAW_PATIENTS p LEFT JOIN RAW.RAW_MEMBERS m USING (member_id);

CREATE OR REPLACE TABLE FACT_ENCOUNTER AS SELECT * FROM RAW.RAW_ENCOUNTERS;
CREATE OR REPLACE TABLE FACT_CLAIM     AS SELECT * FROM RAW.RAW_CLAIMS;
CREATE OR REPLACE TABLE FACT_DIAGNOSIS AS SELECT * FROM RAW.RAW_DIAGNOSES;
CREATE OR REPLACE TABLE FACT_MEDICATION AS SELECT * FROM RAW.RAW_MEDICATIONS;
CREATE OR REPLACE TABLE FACT_LAB       AS SELECT * FROM RAW.RAW_LABS;
CREATE OR REPLACE TABLE FACT_ED_VISIT  AS SELECT * FROM RAW.RAW_ED_VISITS;

/* ---- quality gates: the copilot should not sit on unvalidated data ------- */
CREATE OR REPLACE TABLE DQ_CHECKS AS
SELECT 'orphan_encounters' AS check_name,
       COUNT(*) AS failing_rows, 'encounter without a patient record' AS detail
FROM FACT_ENCOUNTER e LEFT JOIN DIM_PATIENT p USING (patient_id) WHERE p.patient_id IS NULL
UNION ALL
SELECT 'orphan_claims', COUNT(*), 'claim without an encounter record'
FROM FACT_CLAIM c LEFT JOIN FACT_ENCOUNTER e USING (encounter_id) WHERE e.encounter_id IS NULL
UNION ALL
SELECT 'negative_allowed_amount', COUNT(*), 'allowed_amount below zero'
FROM FACT_CLAIM WHERE allowed_amount < 0
UNION ALL
SELECT 'inpatient_missing_admission_source', COUNT(*), 'rejected by REG-CMS-2026-07 data quality controls'
FROM FACT_ENCOUNTER WHERE encounter_type = 'INPATIENT' AND (admission_source IS NULL OR admission_source = 'N/A')
UNION ALL
SELECT 'los_exceeds_stay_window', COUNT(*), 'length_of_stay_days disagrees with admit/discharge dates'
FROM FACT_ENCOUNTER WHERE encounter_type = 'INPATIENT' AND length_of_stay_days <> DATEDIFF('day', start_date, end_date)
UNION ALL
SELECT 'implausible_age', COUNT(*), 'age outside 0-120'
FROM DIM_PATIENT WHERE age_years < 0 OR age_years > 120;

SELECT * FROM DQ_CHECKS ORDER BY failing_rows DESC;
