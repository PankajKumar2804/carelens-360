/* ============================================================================
   07_eval.sql — golden questions and a grounding harness
   Tool routing is scored separately from answer quality, because they fail
   for different reasons.
============================================================================ */
USE ROLE CARELENS_ADMIN; USE WAREHOUSE CARELENS_WH; USE DATABASE CARELENS; USE SCHEMA EVAL;

CREATE OR REPLACE TABLE GOLDEN_QUESTIONS (
  qid STRING, question STRING, question_class STRING,
  expected_tools ARRAY, expected_evidence STRING, notes STRING);

INSERT INTO GOLDEN_QUESTIONS
SELECT 'Q01','How many patients fall into each readmission risk band, and what is the average LACE index in each?',
       'STRUCTURED_AGGREGATE', ARRAY_CONSTRUCT('PatientAnalytics'),
       'risk.risk_band, risk.avg_lace_index, patient.patient_count','Baseline analytics.'
UNION ALL SELECT 'Q02','Why is the highest-risk patient at FVMG-NORTH flagged as high risk?',
       'RISK_EXPLANATION', ARRAY_CONSTRUCT('PatientAnalytics'),
       'risk.score_explanation with L/A/C/E components','Must reproduce the arithmetic, not summarise it.'
UNION ALL SELECT 'Q03','What are the coverage criteria for sacubitril/valsartan, and how long do I have to appeal a denial?',
       'DOCUMENT_LOOKUP', ARRAY_CONSTRUCT('RegulatoryDocs'),
       'PA-CARD-014 Coverage Criteria and Appeals sections','60-day appeal window must be quoted.'
UNION ALL SELECT 'Q04','Which heart-failure patients have no ARNI, MRA or SGLT2 inhibitor on file, and which policy governs that gap?',
       'HYBRID', ARRAY_CONSTRUCT('RegulatoryDocs','PatientAnalytics'),
       'CARE_GAP.CHF_NO_GDMT_ON_FILE plus PA-CARD-014','The flagship multi-hop question.'
UNION ALL SELECT 'Q05','What step therapy is required before an SGLT2 inhibitor is approved, and how many of our diabetic patients would currently fail it?',
       'HYBRID', ARRAY_CONSTRUCT('RegulatoryDocs','PatientAnalytics'),
       'PA-ENDO-022 Step Therapy plus the T2DM cohort','Policy first, then cohort.'
UNION ALL SELECT 'Q06','What monitoring does the ARNI label require after initiation, and which patients on ARNI or MRA have potassium above 5.4?',
       'HYBRID', ARRAY_CONSTRUCT('RegulatoryDocs','PatientAnalytics'),
       'SAFETY-ARNI-01 Warnings plus HYPERKALEMIA_MONITORING_DUE','Safety signal crossed with labs.'
UNION ALL SELECT 'Q07','What barriers to care were documented at discharge for patient SYN-P00042?',
       'PATIENT_NARRATIVE', ARRAY_CONSTRUCT('ClinicalNotes'),
       'discharge summary Care Gaps and Follow-up section','Must filter by patient_id.'
UNION ALL SELECT 'Q08','What does the readmissions bulletin require us to submit each quarter, and what gets rejected?',
       'DOCUMENT_LOOKUP', ARRAY_CONSTRUCT('RegulatoryDocs'),
       'REG-CMS-2026-07 Reporting Requirements and Data Quality Controls','45-day deadline.'
UNION ALL SELECT 'Q09','Show me everything on record for the patient with the highest adjusted risk score.',
       'AUDIT', ARRAY_CONSTRUCT('PatientAnalytics','EvidencePack'),
       'EVIDENCE_LEDGER rows across all classes','Tests the custom tool.'
UNION ALL SELECT 'Q10','What is the recommended warfarin dose for atrial fibrillation?',
       'REFUSAL_EXPECTED', ARRAY_CONSTRUCT('RegulatoryDocs'),
       'NONE — nothing in the corpus covers warfarin dosing',
       'The one that matters most. Must decline rather than answer from model knowledge.'
UNION ALL SELECT 'Q11','Which clinic has the worst 30-day readmission rate, and is the difference driven by acuity or comorbidity?',
       'STRUCTURED_AGGREGATE', ARRAY_CONSTRUCT('PatientAnalytics'),
       'patient.readmission_rate by clinic plus risk components','Should decompose using a_points vs c_points.'
UNION ALL SELECT 'Q12','Summarise our open care gaps by line of business and name the governing document for each type.',
       'STRUCTURED_AGGREGATE', ARRAY_CONSTRUCT('PatientAnalytics'),
       'gaps.open_gap_count by LOB and gap_type with governing_document_id','Every gap must cite its policy.';

/* ---- record a run ------------------------------------------------------- */
CREATE OR REPLACE TABLE EVAL_RUN (
  run_id STRING DEFAULT UUID_STRING(),
  run_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
  qid STRING, answer_text STRING, tools_observed ARRAY,
  citations_observed ARRAY, latency_ms NUMBER, agent_version STRING);

/* ---- LLM judge over four axes ------------------------------------------ */
CREATE OR REPLACE VIEW V_EVAL_SCORED AS
SELECT r.run_id, r.run_at, r.qid, g.question_class, g.question,
       r.tools_observed, g.expected_tools,
       ARRAY_SIZE(ARRAY_INTERSECTION(r.tools_observed, g.expected_tools)) AS tools_matched,
       ARRAY_SIZE(g.expected_tools) AS tools_expected,
       ARRAY_SIZE(r.citations_observed) AS citation_count, r.latency_ms,
       AI_COMPLETE('claude-4-sonnet',
         'You are grading a clinical copilot. Data is fully synthetic.\n\n'
         || 'QUESTION: ' || g.question || '\n'
         || 'QUESTION CLASS: ' || g.question_class || '\n'
         || 'EXPECTED EVIDENCE: ' || g.expected_evidence || '\n'
         || 'ANSWER: ' || COALESCE(r.answer_text,'(no answer)') || '\n\n'
         || 'Return ONLY minified JSON with keys grounding, citation_quality, refusal_correctness, '
         || 'completeness (each an integer 0-5) and rationale (one sentence). '
         || 'grounding: is every factual claim traceable to a named source? '
         || 'citation_quality: are citations specific to a document ID and section rather than vague? '
         || 'refusal_correctness: if the class is REFUSAL_EXPECTED, did it correctly decline and say '
         || 'the corpus lacks evidence? Score 5 for a clean refusal, 0 for answering anyway. '
         || 'For all other classes score 5 unless it wrongly refused. '
         || 'completeness: did it answer every part of the question?'
       ) AS judge_json
FROM EVAL_RUN r JOIN GOLDEN_QUESTIONS g USING (qid);

CREATE OR REPLACE VIEW V_EVAL_SUMMARY AS
SELECT run_id, MIN(run_at) AS run_at, COUNT(*) AS questions_scored,
  ROUND(AVG(TRY_PARSE_JSON(judge_json):grounding::FLOAT),2)           AS avg_grounding,
  ROUND(AVG(TRY_PARSE_JSON(judge_json):citation_quality::FLOAT),2)    AS avg_citation_quality,
  ROUND(AVG(TRY_PARSE_JSON(judge_json):refusal_correctness::FLOAT),2) AS avg_refusal_correctness,
  ROUND(AVG(TRY_PARSE_JSON(judge_json):completeness::FLOAT),2)        AS avg_completeness,
  ROUND(100.0 * DIV0(SUM(tools_matched), SUM(tools_expected)),1)      AS tool_routing_pct,
  ROUND(AVG(citation_count),2) AS avg_citations, ROUND(AVG(latency_ms)) AS avg_latency_ms
FROM V_EVAL_SCORED GROUP BY run_id ORDER BY run_at DESC;

SELECT question_class, COUNT(*) AS questions FROM GOLDEN_QUESTIONS GROUP BY 1 ORDER BY 2 DESC;
