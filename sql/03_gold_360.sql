/* ============================================================================
   03_gold_360.sql — PATIENT_360, MEMBER_360, transparent risk, care gaps,
                     evidence ledger
   Risk here is arithmetic, not inference. Every score carries its own
   explanation and the citation for its methodology.
============================================================================ */
USE ROLE CARELENS_ADMIN; USE WAREHOUSE CARELENS_WH; USE DATABASE CARELENS; USE SCHEMA GOLD;

/* ---- per-domain rollups so the 360 stays one row per patient ------------- */
CREATE OR REPLACE VIEW V_PATIENT_UTILIZATION AS
SELECT patient_id,
  COUNT(*) AS encounter_count,
  COUNT_IF(encounter_type='INPATIENT')  AS inpatient_count,
  COUNT_IF(encounter_type='EMERGENCY')  AS ed_count,
  COUNT_IF(encounter_type='EMERGENCY' AND start_date >= DATEADD('month',-6,CURRENT_DATE)) AS ed_visits_6mo,
  MAX(IFF(encounter_type='INPATIENT', end_date, NULL))            AS last_discharge_date,
  MAX(IFF(encounter_type='INPATIENT', length_of_stay_days, NULL)) AS last_inpatient_los,
  MAX(readmit_30d) AS any_readmit_30d
FROM CURATED.FACT_ENCOUNTER GROUP BY patient_id;

CREATE OR REPLACE VIEW V_PATIENT_LAST_ADMISSION AS
SELECT patient_id, encounter_id, start_date, end_date, length_of_stay_days,
       admission_source, discharge_disposition, facility
FROM CURATED.FACT_ENCOUNTER
WHERE encounter_type='INPATIENT'
QUALIFY ROW_NUMBER() OVER (PARTITION BY patient_id ORDER BY end_date DESC) = 1;

CREATE OR REPLACE VIEW V_PATIENT_BURDEN AS
SELECT patient_id,
  SUM(IFF(clinical_status='active', charlson_weight, 0)) AS charlson_raw,
  LEAST(SUM(IFF(clinical_status='active', charlson_weight, 0)), 5) AS charlson_capped,
  COUNT_IF(clinical_status='active') AS active_condition_count,
  COUNT_IF(hcc_flag=1 AND clinical_status='active') AS hcc_condition_count,
  BOOLOR_AGG(icd10_code='I50.9' AND clinical_status='active') AS has_chf,
  BOOLOR_AGG(icd10_code LIKE 'E11%' AND clinical_status='active') AS has_t2dm,
  BOOLOR_AGG(icd10_code LIKE 'N18%' AND clinical_status='active') AS has_ckd,
  BOOLOR_AGG(icd10_code LIKE 'J44%' AND clinical_status='active') AS has_copd
FROM CURATED.FACT_DIAGNOSIS GROUP BY patient_id;

CREATE OR REPLACE VIEW V_PATIENT_PHARMACY AS
SELECT patient_id,
  COUNT_IF(active_flag=1) AS active_med_count,
  MIN(IFF(active_flag=1, adherence_pdc, NULL)) AS worst_pdc,
  BOOLOR_AGG(active_flag=1 AND drug_class='ARNI')            AS on_arni,
  BOOLOR_AGG(active_flag=1 AND drug_class='MRA')             AS on_mra,
  BOOLOR_AGG(active_flag=1 AND drug_class='SGLT2 inhibitor') AS on_sglt2,
  BOOLOR_AGG(active_flag=1 AND drug_class='biguanide')       AS on_metformin,
  BOOLOR_AGG(active_flag=1 AND drug_class='loop diuretic')   AS on_loop_diuretic
FROM CURATED.FACT_MEDICATION GROUP BY patient_id;

CREATE OR REPLACE VIEW V_PATIENT_LABS AS
SELECT patient_id,
  MAX(IFF(loinc_code='4548-4', result_value, NULL))  AS latest_a1c,
  MAX(IFF(loinc_code='2160-0', result_value, NULL))  AS latest_creatinine,
  MAX(IFF(loinc_code='33762-6', result_value, NULL)) AS latest_ntprobnp,
  MAX(IFF(loinc_code='2823-3', result_value, NULL))  AS latest_potassium,
  COUNT_IF(abnormal_flag=1) AS abnormal_result_count
FROM CURATED.FACT_LAB GROUP BY patient_id;

CREATE OR REPLACE VIEW V_PATIENT_FINANCIAL AS
SELECT patient_id,
  SUM(allowed_amount) AS total_allowed_amount,
  SUM(paid_amount)    AS total_paid_amount,
  SUM(member_liability) AS total_member_liability,
  COUNT_IF(claim_status='DENIED') AS denied_claim_count,
  COUNT(*) AS claim_count
FROM CURATED.FACT_CLAIM GROUP BY patient_id;

/* ---- the 360 ------------------------------------------------------------ */
CREATE OR REPLACE TABLE PATIENT_360 AS
SELECT
  p.patient_id, p.member_id, p.full_name, p.first_name, p.last_name,
  p.birth_date, p.age_years, p.sex, p.city, p.state, p.postal_code,
  p.primary_language, p.pcp_npi,
  p.payer_name, p.plan_id, p.line_of_business, p.risk_program, p.attributed_clinic,
  COALESCE(u.encounter_count,0) AS encounter_count,
  COALESCE(u.inpatient_count,0) AS inpatient_count,
  COALESCE(u.ed_count,0)        AS ed_count,
  COALESCE(u.ed_visits_6mo,0)   AS ed_visits_6mo,
  u.last_discharge_date, u.last_inpatient_los,
  COALESCE(u.any_readmit_30d,0) AS any_readmit_30d,
  la.admission_source AS last_admission_source,
  la.discharge_disposition AS last_discharge_disposition,
  la.encounter_id AS last_inpatient_encounter_id,
  COALESCE(b.charlson_raw,0) AS charlson_raw,
  COALESCE(b.charlson_capped,0) AS charlson_capped,
  COALESCE(b.active_condition_count,0) AS active_condition_count,
  COALESCE(b.hcc_condition_count,0) AS hcc_condition_count,
  COALESCE(b.has_chf,FALSE) AS has_chf, COALESCE(b.has_t2dm,FALSE) AS has_t2dm,
  COALESCE(b.has_ckd,FALSE) AS has_ckd, COALESCE(b.has_copd,FALSE) AS has_copd,
  COALESCE(ph.active_med_count,0) AS active_med_count, ph.worst_pdc,
  COALESCE(ph.on_arni,FALSE) AS on_arni, COALESCE(ph.on_mra,FALSE) AS on_mra,
  COALESCE(ph.on_sglt2,FALSE) AS on_sglt2, COALESCE(ph.on_metformin,FALSE) AS on_metformin,
  lb.latest_a1c, lb.latest_creatinine, lb.latest_ntprobnp, lb.latest_potassium,
  COALESCE(lb.abnormal_result_count,0) AS abnormal_result_count,
  COALESCE(f.total_allowed_amount,0) AS total_allowed_amount,
  COALESCE(f.total_paid_amount,0) AS total_paid_amount,
  COALESCE(f.denied_claim_count,0) AS denied_claim_count,
  COALESCE(f.claim_count,0) AS claim_count,
  COALESCE(sig.has_barrier, FALSE) AS documented_barrier_to_care,
  sig.barrier_to_care, sig.adverse_event AS documented_adverse_event,
  sig.followup_days AS recommended_followup_days,
  'SYNTHETIC' AS data_classification,
  CURRENT_TIMESTAMP() AS built_at
FROM CURATED.DIM_PATIENT p
LEFT JOIN V_PATIENT_UTILIZATION u   USING (patient_id)
LEFT JOIN V_PATIENT_LAST_ADMISSION la USING (patient_id)
LEFT JOIN V_PATIENT_BURDEN b        USING (patient_id)
LEFT JOIN V_PATIENT_PHARMACY ph     USING (patient_id)
LEFT JOIN V_PATIENT_LABS lb         USING (patient_id)
LEFT JOIN V_PATIENT_FINANCIAL f     USING (patient_id)
LEFT JOIN (
  SELECT patient_id, BOOLOR_AGG(has_barrier) AS has_barrier,
         MAX(barrier_to_care) AS barrier_to_care, MAX(adverse_event) AS adverse_event,
         MIN(followup_days) AS followup_days
  FROM CURATED.V_DOC_SAFETY_SIGNAL GROUP BY patient_id) sig USING (patient_id);

CREATE OR REPLACE TABLE MEMBER_360 AS
SELECT m.member_id, m.patient_id, m.payer_name, m.plan_id, m.line_of_business,
       m.risk_program, m.attributed_clinic, m.enroll_start,
       DATEDIFF('month', m.enroll_start, CURRENT_DATE) AS months_enrolled,
       f.claim_count, f.denied_claim_count,
       DIV0(f.denied_claim_count, f.claim_count) AS denial_rate,
       f.total_allowed_amount, f.total_paid_amount, f.total_member_liability,
       'SYNTHETIC' AS data_classification
FROM RAW.RAW_MEMBERS m LEFT JOIN V_PATIENT_FINANCIAL f USING (patient_id);

/* ---- transparent risk ---------------------------------------------------
   LACE: Length of stay, Acuity of admission, Comorbidity, ED visits.
   Published index kept unmodified; local modifiers live in separate columns
   so nothing silently distorts a cited methodology.                         */
CREATE OR REPLACE TABLE RISK_READMISSION AS
WITH pts AS (
  SELECT patient_id, attributed_clinic, line_of_business,
    CASE WHEN last_inpatient_los IS NULL THEN 0
         WHEN last_inpatient_los >= 14 THEN 7
         WHEN last_inpatient_los >= 7  THEN 5
         WHEN last_inpatient_los >= 4  THEN 4
         ELSE last_inpatient_los END                        AS l_points,
    IFF(last_admission_source = 'EMERGENCY', 3, 0)          AS a_points,
    charlson_capped                                         AS c_points,
    LEAST(ed_visits_6mo, 4)                                 AS e_points,
    IFF(worst_pdc IS NOT NULL AND worst_pdc < 0.80, 1, 0)   AS mod_adherence_point,
    IFF(documented_barrier_to_care, 1, 0)                   AS mod_barrier_point,
    last_inpatient_los, last_admission_source, charlson_raw,
    ed_visits_6mo, worst_pdc, barrier_to_care, last_discharge_date
  FROM PATIENT_360
)
SELECT patient_id, attributed_clinic, line_of_business,
  l_points, a_points, c_points, e_points,
  (l_points + a_points + c_points + e_points) AS lace_index,
  mod_adherence_point, mod_barrier_point,
  (l_points + a_points + c_points + e_points + mod_adherence_point + mod_barrier_point)
    AS carelens_adjusted_score,
  CASE WHEN (l_points + a_points + c_points + e_points) >= 10 THEN 'HIGH'
       WHEN (l_points + a_points + c_points + e_points) >= 5  THEN 'INTERMEDIATE'
       ELSE 'LOW' END AS risk_band,
  'LACE ' || (l_points + a_points + c_points + e_points) || ' = '
    || 'L' || l_points || ' (' || COALESCE('last LOS ' || last_inpatient_los || 'd', 'no inpatient stay') || ') + '
    || 'A' || a_points || ' (admission source ' || COALESCE(last_admission_source,'none') || ') + '
    || 'C' || c_points || ' (Charlson ' || charlson_raw || ', capped at 5) + '
    || 'E' || e_points || ' (' || ed_visits_6mo || ' ED visits in prior 6 months)'
    || IFF(mod_adherence_point + mod_barrier_point > 0,
           '. CareLens local modifiers +' || (mod_adherence_point + mod_barrier_point)
           || ' ('
           || TRIM(IFF(mod_adherence_point=1, 'lowest active-medication PDC ' || worst_pdc || '; ', '')
                || IFF(mod_barrier_point=1, 'documented barrier: ' || COALESCE(barrier_to_care,'yes'), ''))
           || ')', '')
    AS score_explanation,
  'LACE index (van Walraven et al., CMAJ 2010). Additive, four components, max 19. '
    || 'Bands: 0-4 LOW, 5-9 INTERMEDIATE, 10+ HIGH. '
    || 'Modifier columns are CARELENS_LOCAL_HEURISTIC and are excluded from lace_index.'
    AS methodology_citation,
  last_discharge_date, CURRENT_TIMESTAMP() AS scored_at
FROM pts;

/* ---- care gaps: every rule names the document that governs it ----------- */
CREATE OR REPLACE TABLE CARE_GAP AS
SELECT patient_id, attributed_clinic, line_of_business, gap_type, gap_detail,
       governing_document_id, gap_status, CURRENT_TIMESTAMP() AS identified_at
FROM (
  SELECT patient_id, attributed_clinic, line_of_business,
         'CHF_NO_GDMT_ON_FILE' AS gap_type,
         'Active heart failure with no ARNI, MRA or SGLT2 inhibitor on the active medication list' AS gap_detail,
         'PA-CARD-014' AS governing_document_id, 'OPEN' AS gap_status
  FROM PATIENT_360 WHERE has_chf AND NOT on_arni AND NOT on_mra AND NOT on_sglt2
  UNION ALL
  SELECT patient_id, attributed_clinic, line_of_business,
         'T2DM_A1C_ABOVE_TARGET_NO_STEP_UP',
         'HbA1c at or above 7.0% with metformin on file and no SGLT2 inhibitor added',
         'PA-ENDO-022', 'OPEN'
  FROM PATIENT_360 WHERE has_t2dm AND latest_a1c >= 7.0 AND on_metformin AND NOT on_sglt2
  UNION ALL
  SELECT patient_id, attributed_clinic, line_of_business,
         'CKD_SGLT2_ELIGIBLE_NOT_ON_THERAPY',
         'Chronic kidney disease documented and eligible for SGLT2 inhibitor per coverage criteria',
         'PA-ENDO-022', 'OPEN'
  FROM PATIENT_360 WHERE has_ckd AND NOT on_sglt2
  UNION ALL
  SELECT patient_id, attributed_clinic, line_of_business,
         'POST_DISCHARGE_FOLLOWUP_AT_RISK',
         'Inpatient discharge with a documented barrier to care, against a 14-day follow-up measure',
         'QM-HEDIS-LIKE-03', 'OPEN'
  FROM PATIENT_360 WHERE last_discharge_date IS NOT NULL AND documented_barrier_to_care
  UNION ALL
  SELECT patient_id, attributed_clinic, line_of_business,
         'LOW_ADHERENCE_RENEWAL_RISK',
         'Lowest active-medication PDC below 0.80, which fails the renewal adherence requirement',
         'PA-ENDO-022', 'OPEN'
  FROM PATIENT_360 WHERE worst_pdc < 0.80
  UNION ALL
  SELECT patient_id, attributed_clinic, line_of_business,
         'HYPERKALEMIA_MONITORING_DUE',
         'Serum potassium above 5.4 mmol/L with an ARNI or MRA on file; label requires monitoring',
         'SAFETY-ARNI-01', 'OPEN'
  FROM PATIENT_360 WHERE latest_potassium > 5.4 AND (on_arni OR on_mra)
);

/* ---- evidence ledger: structured facts and document chunks, one shape ----
   This is what makes a number as traceable as a quote.                      */
CREATE OR REPLACE VIEW EVIDENCE_LEDGER AS
SELECT 'DOCUMENT' AS evidence_class, doc_id AS source_id, citation_label AS locator,
       patient_id, doc_type AS source_type, section_heading AS context,
       LEFT(chunk_text, 1200) AS evidence_text, effective_date AS as_of_date
FROM CURATED.DOC_CHUNK
UNION ALL
SELECT 'STRUCTURED', 'GOLD.RISK_READMISSION', 'risk_band + lace_index for ' || patient_id,
       patient_id, 'RISK_SCORE', 'LACE components L/A/C/E',
       score_explanation || ' | Methodology: ' || methodology_citation, scored_at::DATE
FROM RISK_READMISSION
UNION ALL
SELECT 'STRUCTURED', 'GOLD.CARE_GAP', gap_type || ' governed by ' || governing_document_id,
       patient_id, 'CARE_GAP', gap_type, gap_detail, identified_at::DATE
FROM CARE_GAP
UNION ALL
SELECT 'STRUCTURED', 'CURATED.FACT_CLAIM', 'claim ' || claim_id, patient_id, 'CLAIM',
       claim_status || COALESCE(' / ' || NULLIF(denial_reason,''), ''),
       'Service date ' || service_date || ', allowed ' || allowed_amount
         || ', paid ' || paid_amount || ', status ' || claim_status, service_date
FROM CURATED.FACT_CLAIM;

SELECT risk_band, COUNT(*) AS patients, ROUND(AVG(lace_index),2) AS avg_lace
FROM RISK_READMISSION GROUP BY 1 ORDER BY avg_lace DESC;
