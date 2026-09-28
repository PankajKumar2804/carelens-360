/* ============================================================================
   04_semantic_view.sql — governed semantic view for Cortex Analyst
   Clause order is enforced: TABLES, RELATIONSHIPS, FACTS, DIMENSIONS, METRICS.
   Text-to-SQL accuracy is a modelling problem, so the synonyms matter more
   than the prompt does.
============================================================================ */
USE ROLE CARELENS_ADMIN; USE WAREHOUSE CARELENS_WH; USE DATABASE CARELENS; USE SCHEMA AI;

CREATE OR REPLACE SEMANTIC VIEW PATIENT_360_SV
  TABLES (
    patient AS CARELENS.GOLD.PATIENT_360 PRIMARY KEY (patient_id)
      WITH SYNONYMS ('patients','people','panel','member roster','patient 360')
      COMMENT = 'One row per patient: demographics, coverage, utilisation, conditions, pharmacy, labs, cost. Synthetic.',
    member AS CARELENS.GOLD.MEMBER_360 PRIMARY KEY (member_id)
      WITH SYNONYMS ('members','enrollees','coverage','plan membership')
      COMMENT = 'One row per member: plan, line of business, enrolment, claim economics.',
    risk AS CARELENS.GOLD.RISK_READMISSION PRIMARY KEY (patient_id)
      WITH SYNONYMS ('risk','readmission risk','risk stratification','LACE','risk tier')
      COMMENT = 'Transparent additive readmission risk with component breakdown and explanation.',
    gaps AS CARELENS.GOLD.CARE_GAP
      WITH SYNONYMS ('care gaps','gaps in care','quality gaps','open gaps')
      COMMENT = 'Deterministic care gaps, each naming the document that governs it.',
    enc AS CARELENS.CURATED.FACT_ENCOUNTER PRIMARY KEY (encounter_id)
      WITH SYNONYMS ('encounters','visits','admissions','stays')
      COMMENT = 'Encounter grain: inpatient, outpatient, emergency, telehealth.',
    clm AS CARELENS.CURATED.FACT_CLAIM PRIMARY KEY (claim_id)
      WITH SYNONYMS ('claims','billing','remittance')
      COMMENT = 'Claim grain with allowed, paid, liability, status and denial reason.',
    dx AS CARELENS.CURATED.FACT_DIAGNOSIS
      WITH SYNONYMS ('diagnoses','conditions','problems','problem list')
      COMMENT = 'Diagnosis grain with ICD-10 code, Charlson weight and HCC flag.',
    rx AS CARELENS.CURATED.FACT_MEDICATION
      WITH SYNONYMS ('medications','drugs','prescriptions','pharmacy')
      COMMENT = 'Medication grain with drug class, days supply and adherence PDC.'
  )
  RELATIONSHIPS (
    member_to_patient AS member (patient_id) REFERENCES patient (patient_id),
    risk_to_patient   AS risk   (patient_id) REFERENCES patient (patient_id),
    gaps_to_patient   AS gaps   (patient_id) REFERENCES patient (patient_id),
    enc_to_patient    AS enc    (patient_id) REFERENCES patient (patient_id),
    clm_to_patient    AS clm    (patient_id) REFERENCES patient (patient_id),
    dx_to_patient     AS dx     (patient_id) REFERENCES patient (patient_id),
    rx_to_patient     AS rx     (patient_id) REFERENCES patient (patient_id)
  )
  FACTS (
    patient.age_years AS age_years COMMENT = 'Age in years at query time',
    patient.ed_visits_6mo AS ed_visits_6mo COMMENT = 'Emergency visits in the prior 6 months',
    patient.charlson_raw AS charlson_raw COMMENT = 'Uncapped Charlson comorbidity weight',
    patient.total_allowed_amount AS total_allowed_amount,
    patient.total_paid_amount AS total_paid_amount,
    patient.denied_claim_count AS denied_claim_count,
    patient.claim_count AS claim_count,
    patient.worst_pdc AS worst_pdc COMMENT = 'Lowest proportion-of-days-covered across active medications',
    patient.latest_a1c AS latest_a1c,
    patient.latest_potassium AS latest_potassium,
    patient.any_readmit_30d AS any_readmit_30d COMMENT = '1 if any inpatient stay was followed by a 30-day readmission',
    risk.lace_index AS lace_index COMMENT = 'Published LACE index, 0-19, unmodified',
    risk.carelens_adjusted_score AS carelens_adjusted_score COMMENT = 'LACE plus CareLens local modifiers',
    risk.l_points AS l_points, risk.a_points AS a_points,
    risk.c_points AS c_points, risk.e_points AS e_points,
    enc.length_of_stay_days AS length_of_stay_days,
    enc.readmit_30d AS readmit_30d,
    clm.allowed_amount AS allowed_amount,
    clm.paid_amount AS paid_amount,
    clm.member_liability AS member_liability,
    rx.adherence_pdc AS adherence_pdc,
    dx.charlson_weight AS charlson_weight
  )
  DIMENSIONS (
    patient.patient_id AS patient_id WITH SYNONYMS ('patient identifier','mrn') COMMENT = 'Synthetic patient key',
    patient.full_name AS full_name WITH SYNONYMS ('name','patient name') COMMENT = 'Masked by policy for non-clinical roles',
    patient.sex AS sex WITH SYNONYMS ('gender'),
    patient.state AS state WITH SYNONYMS ('province','region'),
    patient.attributed_clinic AS attributed_clinic
      WITH SYNONYMS ('clinic','site','practice','panel','location')
      COMMENT = 'Clinic the patient is attributed to; also drives row-level access',
    patient.line_of_business AS line_of_business
      WITH SYNONYMS ('LOB','product','coverage type','commercial medicare medicaid'),
    patient.payer_name AS payer_name WITH SYNONYMS ('payer','plan sponsor','insurer'),
    patient.plan_id AS plan_id WITH SYNONYMS ('plan','benefit plan'),
    patient.risk_program AS risk_program WITH SYNONYMS ('program','care management program'),
    patient.primary_language AS primary_language WITH SYNONYMS ('language'),
    patient.age_band AS CASE WHEN age_years < 45 THEN '19-44'
                             WHEN age_years < 65 THEN '45-64'
                             ELSE '65+' END
      WITH SYNONYMS ('age group','age bracket','age cohort')
      COMMENT = 'Pre-defined age buckets so cohort questions do not invent boundaries',
    patient.has_chf AS has_chf WITH SYNONYMS ('heart failure','CHF','congestive heart failure'),
    patient.has_t2dm AS has_t2dm WITH SYNONYMS ('diabetes','type 2 diabetes','T2DM'),
    patient.has_ckd AS has_ckd WITH SYNONYMS ('kidney disease','CKD','renal disease'),
    patient.has_copd AS has_copd WITH SYNONYMS ('COPD','chronic lung disease'),
    patient.on_arni AS on_arni WITH SYNONYMS ('ARNI','sacubitril valsartan','entresto-like'),
    patient.on_mra AS on_mra WITH SYNONYMS ('MRA','spironolactone','aldosterone antagonist'),
    patient.on_sglt2 AS on_sglt2 WITH SYNONYMS ('SGLT2','SGLT2 inhibitor','flozin'),
    patient.on_metformin AS on_metformin WITH SYNONYMS ('metformin','biguanide'),
    patient.documented_barrier_to_care AS documented_barrier_to_care
      WITH SYNONYMS ('barrier','social barrier','SDOH barrier')
      COMMENT = 'Derived from discharge narrative via document extraction',
    risk.risk_band AS risk_band
      WITH SYNONYMS ('risk tier','risk level','risk category','acuity','stratification')
      COMMENT = 'LOW 0-4, INTERMEDIATE 5-9, HIGH 10+ on the LACE index',
    risk.score_explanation AS score_explanation
      WITH SYNONYMS ('why','explanation','risk reason','rationale','breakdown')
      COMMENT = 'Plain-language arithmetic behind the score. Always return this with a risk value.',
    risk.methodology_citation AS methodology_citation
      WITH SYNONYMS ('methodology','citation','basis','source of the score'),
    gaps.gap_type AS gap_type WITH SYNONYMS ('gap','gap category','measure'),
    gaps.gap_detail AS gap_detail WITH SYNONYMS ('gap description'),
    gaps.governing_document_id AS governing_document_id
      WITH SYNONYMS ('policy','governing policy','which document','specification')
      COMMENT = 'Document ID that defines this gap. Always return this with a gap.',
    gaps.gap_status AS gap_status,
    enc.encounter_type AS encounter_type WITH SYNONYMS ('visit type','setting','care setting'),
    enc.admission_source AS admission_source WITH SYNONYMS ('acuity','how admitted','admit source'),
    enc.discharge_disposition AS discharge_disposition WITH SYNONYMS ('discharged to','disposition'),
    enc.facility AS facility WITH SYNONYMS ('hospital','site of care'),
    clm.claim_status AS claim_status WITH SYNONYMS ('status','paid denied pending'),
    clm.denial_reason AS denial_reason WITH SYNONYMS ('why denied','denial','rejection reason'),
    clm.claim_type AS claim_type WITH SYNONYMS ('facility or professional'),
    dx.icd10_code AS icd10_code WITH SYNONYMS ('diagnosis code','ICD','ICD-10'),
    dx.diagnosis_description AS diagnosis_description WITH SYNONYMS ('condition name','diagnosis'),
    rx.drug_class AS drug_class WITH SYNONYMS ('medication class','therapeutic class'),
    rx.medication_name AS medication_name WITH SYNONYMS ('drug','medication')
  )
  METRICS (
    patient.patient_count AS COUNT(DISTINCT patient.patient_id)
      WITH SYNONYMS ('patients','how many patients','headcount','panel size'),
    patient.avg_age AS AVG(patient.age_years) WITH SYNONYMS ('average age','mean age'),
    patient.total_cost AS SUM(patient.total_allowed_amount)
      WITH SYNONYMS ('cost','spend','total allowed','allowed spend'),
    patient.cost_per_patient AS DIV0(SUM(patient.total_allowed_amount), COUNT(DISTINCT patient.patient_id))
      WITH SYNONYMS ('cost per patient','PMPY','average cost'),
    patient.readmission_rate AS DIV0(SUM(patient.any_readmit_30d), COUNT(DISTINCT patient.patient_id))
      WITH SYNONYMS ('readmission rate','30 day readmission rate','readmit rate')
      COMMENT = 'Share of patients with any 30-day readmission. DIV0 so empty cohorts return 0.',
    patient.avg_worst_pdc AS AVG(patient.worst_pdc)
      WITH SYNONYMS ('adherence','average PDC','medication adherence'),
    risk.avg_lace_index AS AVG(risk.lace_index)
      WITH SYNONYMS ('average risk score','mean LACE','average LACE index'),
    risk.high_risk_count AS COUNT(DISTINCT CASE WHEN risk.risk_band = 'HIGH' THEN risk.patient_id END)
      WITH SYNONYMS ('high risk patients','number at high risk'),
    risk.high_risk_share AS DIV0(
        COUNT(DISTINCT CASE WHEN risk.risk_band = 'HIGH' THEN risk.patient_id END),
        COUNT(DISTINCT risk.patient_id))
      WITH SYNONYMS ('percent high risk','share high risk'),
    gaps.open_gap_count AS COUNT(*) WITH SYNONYMS ('gaps','number of gaps','open gaps'),
    gaps.patients_with_gaps AS COUNT(DISTINCT gaps.patient_id)
      WITH SYNONYMS ('patients with a gap','how many have gaps'),
    enc.encounter_total AS COUNT(DISTINCT enc.encounter_id) WITH SYNONYMS ('visits','encounters'),
    enc.avg_length_of_stay AS AVG(enc.length_of_stay_days) WITH SYNONYMS ('ALOS','average LOS','length of stay'),
    clm.total_allowed AS SUM(clm.allowed_amount) WITH SYNONYMS ('allowed amount','total allowed'),
    clm.total_paid AS SUM(clm.paid_amount) WITH SYNONYMS ('paid','total paid'),
    clm.denial_rate AS DIV0(COUNT(CASE WHEN clm.claim_status = 'DENIED' THEN 1 END), COUNT(*))
      WITH SYNONYMS ('denial rate','percent denied','rejection rate')
  )
  COMMENT = 'CareLens 360 governed semantic layer. FULLY SYNTHETIC DATA.'

  /* ---- guidance the generator reads (inline on CREATE, not ALTER) -------- */
  AI_SQL_GENERATION 'Rules for generating SQL against this view:
1. Whenever a risk score or risk band is returned, also return risk.score_explanation so the arithmetic travels with the number.
2. Whenever a care gap is returned, also return gaps.governing_document_id.
3. Prefer risk.lace_index over risk.carelens_adjusted_score unless the user asks for the adjusted score.
4. Use patient.age_band for age cohort questions rather than deriving new buckets.
5. Filters on boolean condition and medication dimensions are TRUE/FALSE, not 1/0.
6. All data is synthetic. Never caveat that a specific real person may be affected.'

  AI_VERIFIED_QUERIES (
    high_risk_panel_with_reasons AS (
      QUESTION 'Which patients are high risk for readmission and why?'
      SQL 'SELECT * FROM SEMANTIC_VIEW(CARELENS.AI.PATIENT_360_SV DIMENSIONS risk.patient_id, risk.risk_band, risk.score_explanation, patient.attributed_clinic METRICS risk.avg_lace_index) WHERE risk_band = ''HIGH'' ORDER BY avg_lace_index DESC'
    ),
    readmission_rate_by_clinic AS (
      QUESTION 'What is the 30-day readmission rate by clinic?'
      SQL 'SELECT * FROM SEMANTIC_VIEW(CARELENS.AI.PATIENT_360_SV DIMENSIONS patient.attributed_clinic METRICS patient.patient_count, patient.readmission_rate) ORDER BY readmission_rate DESC'
    ),
    care_gaps_by_lob AS (
      QUESTION 'How many open care gaps are there by line of business and gap type?'
      SQL 'SELECT * FROM SEMANTIC_VIEW(CARELENS.AI.PATIENT_360_SV DIMENSIONS patient.line_of_business, gaps.gap_type, gaps.governing_document_id METRICS gaps.open_gap_count) ORDER BY open_gap_count DESC'
    ),
    denial_reasons_ranked AS (
      QUESTION 'What are the most common claim denial reasons?'
      SQL 'SELECT * FROM SEMANTIC_VIEW(CARELENS.AI.PATIENT_360_SV DIMENSIONS clm.denial_reason METRICS clm.denial_rate, clm.total_allowed) ORDER BY denial_rate DESC'
    )
  );

SELECT * FROM SEMANTIC_VIEW(PATIENT_360_SV
  DIMENSIONS patient.attributed_clinic, risk.risk_band
  METRICS patient.patient_count, risk.avg_lace_index)
ORDER BY attributed_clinic, risk_band;
