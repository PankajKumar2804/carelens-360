/* ============================================================================
   02_documents.sql — parse → metadata (regex first, AI_EXTRACT fallback)
                      → section-aware chunking → safety signal mining
============================================================================ */
USE ROLE CARELENS_ADMIN; USE WAREHOUSE CARELENS_WH; USE DATABASE CARELENS; USE SCHEMA CURATED;

ALTER STAGE RAW.DOC_STAGE REFRESH;

/* ---- 1. parse ------------------------------------------------------------ */
CREATE OR REPLACE TABLE DOC_RAW AS
SELECT
  REGEXP_REPLACE(METADATA$FILENAME, '^.*/', '') AS file_name,
  METADATA$FILENAME                             AS stage_path,
  $1::STRING                                    AS doc_text
FROM @RAW.DOC_STAGE (FILE_FORMAT => 'RAW.WHOLE_FILE_TEXT', PATTERN => '.*[.]md');

/* PDF / DOCX path — enable when the corpus includes binary documents.
   AI_PARSE_DOCUMENT in LAYOUT mode preserves headings and tables, which is
   what makes section-level citation possible for those formats too.

INSERT INTO DOC_RAW
SELECT REGEXP_REPLACE(RELATIVE_PATH,'^.*/','') , RELATIVE_PATH,
       AI_PARSE_DOCUMENT(TO_FILE('@RAW.DOC_STAGE', RELATIVE_PATH),
                         {'mode':'LAYOUT'}):content::STRING
FROM DIRECTORY(@RAW.DOC_STAGE) WHERE RELATIVE_PATH ILIKE '%.pdf';
*/

/* ---- 2. metadata: deterministic regex first ------------------------------
   Most documents here carry a predictable header block, so regex is free and
   layout-stable. AI_EXTRACT only fills the gaps, which keeps cost near zero
   for well-formed sources while still ingesting an unfamiliar layout.        */
CREATE OR REPLACE TABLE DOC_METADATA AS
WITH regexed AS (
  SELECT
    file_name, stage_path, doc_text,
    NULLIF(TRIM(REGEXP_SUBSTR(doc_text, '\\*\\*Document ID:\\*\\*\\s*([^\\n]+)', 1, 1, 'e', 1)), '') AS doc_id_rx,
    NULLIF(TRIM(REGEXP_SUBSTR(doc_text, '\\*\\*Document Type:\\*\\*\\s*([^\\n]+)', 1, 1, 'e', 1)), '') AS doc_type_rx,
    NULLIF(TRIM(REGEXP_SUBSTR(doc_text, '\\*\\*Owner:\\*\\*\\s*([^\\n]+)', 1, 1, 'e', 1)), '') AS owner_rx,
    NULLIF(TRIM(REGEXP_SUBSTR(doc_text, '\\*\\*Effective Date:\\*\\*\\s*([0-9]{4}-[0-9]{2}-[0-9]{2})', 1, 1, 'e', 1)), '') AS eff_rx,
    NULLIF(TRIM(REGEXP_SUBSTR(doc_text, '\\*\\*Patient ID:\\*\\*\\s*(SYN-P[0-9]+)', 1, 1, 'e', 1)), '') AS patient_rx,
    NULLIF(TRIM(REGEXP_SUBSTR(doc_text, '\\*\\*Encounter ID:\\*\\*\\s*(SYN-E[0-9A-F]+)', 1, 1, 'e', 1)), '') AS encounter_rx,
    NULLIF(TRIM(REGEXP_SUBSTR(doc_text, '^#\\s+([^\\n]+)', 1, 1, 'e', 1)), '') AS title_rx
  FROM DOC_RAW
),
ai_filled AS (
  SELECT r.*,
    CASE WHEN r.doc_id_rx IS NULL OR r.doc_type_rx IS NULL OR r.eff_rx IS NULL
         THEN AI_EXTRACT(
                text => LEFT(r.doc_text, 4000),
                responseFormat => {
                  'document_id'   : 'What is the document identifier?',
                  'document_type' : 'Classify as DISCHARGE_SUMMARY, UTILIZATION_POLICY, REGULATORY_BULLETIN, DRUG_SAFETY_LABEL or QUALITY_MEASURE',
                  'owner'         : 'Which organisation owns or issued this document?',
                  'effective_date': 'What is the effective date in YYYY-MM-DD form?',
                  'title'         : 'What is the document title?'
                })
    END AS ai_meta
  FROM regexed r
)
SELECT
  COALESCE(doc_id_rx, ai_meta:response:document_id::STRING,
           'DS-' || COALESCE(encounter_rx, file_name))                AS doc_id,
  file_name, stage_path,
  COALESCE(title_rx, ai_meta:response:title::STRING)                  AS doc_title,
  COALESCE(doc_type_rx, ai_meta:response:document_type::STRING,
           IFF(file_name ILIKE 'discharge%', 'DISCHARGE_SUMMARY', 'UNKNOWN')) AS doc_type,
  COALESCE(owner_rx, ai_meta:response:owner::STRING, 'CareLens Synthetic Health System') AS issuing_owner,
  TRY_TO_DATE(COALESCE(eff_rx, ai_meta:response:effective_date::STRING)) AS effective_date,
  patient_rx    AS patient_id,
  encounter_rx  AS encounter_id,
  IFF(patient_rx IS NOT NULL, 'PATIENT_SPECIFIC', 'INSTITUTIONAL') AS scope,
  LENGTH(doc_text) AS char_count,
  IFF(ai_meta IS NULL, 'REGEX', 'REGEX+AI_EXTRACT') AS extraction_path,
  doc_text
FROM ai_filled;

/* ---- 3. chunk -----------------------------------------------------------
   Splitting on '\n## ' before anything else makes chunks align with document
   sections, which is what lets a citation name a section instead of a file.  */
CREATE OR REPLACE TABLE DOC_CHUNK AS
SELECT
  m.doc_id, m.file_name, m.doc_title, m.doc_type, m.issuing_owner,
  m.effective_date, m.patient_id, m.encounter_id, m.scope,
  c.INDEX                                   AS chunk_index,
  c.VALUE::STRING                           AS chunk_text,
  COALESCE(
    NULLIF(TRIM(REGEXP_SUBSTR(c.VALUE::STRING, '##\\s+([^\\n]+)', 1, 1, 'e', 1)), ''),
    'Header'
  )                                         AS section_heading,
  m.doc_id || ' — ' || COALESCE(
    NULLIF(TRIM(REGEXP_SUBSTR(c.VALUE::STRING, '##\\s+([^\\n]+)', 1, 1, 'e', 1)), ''),
    'Header') || ' (chunk ' || c.INDEX || ')' AS citation_label
FROM DOC_METADATA m,
     LATERAL FLATTEN(SNOWFLAKE.CORTEX.SPLIT_TEXT_RECURSIVE_CHARACTER(
       m.doc_text, 'markdown', 900, 150,
       ARRAY_CONSTRUCT('\n## ', '\n\n', '\n', ' ', ''))) c;

/* ---- 4. mine the narrative into structured signal -----------------------
   This view is where the unstructured and structured sides genuinely meet:
   a barrier to care written in prose becomes a point on the risk score.      */
CREATE OR REPLACE TABLE DOC_SAFETY_SIGNAL AS
SELECT
  doc_id, patient_id, encounter_id,
  AI_EXTRACT(
    text => doc_text,
    responseFormat => {
      'adverse_event'     : 'Describe any adverse drug event or medication-related safety issue, or say NONE',
      'barrier_to_care'   : 'What barrier to care is documented (transportation, cost, caregiver support), or NONE',
      'followup_days'     : 'Within how many days should the patient follow up? Return only the number',
      'followup_specialty': 'Which specialty should the follow-up be with?'
    }) AS signal
FROM DOC_METADATA
WHERE doc_type = 'DISCHARGE_SUMMARY' AND patient_id IS NOT NULL;

CREATE OR REPLACE VIEW V_DOC_SAFETY_SIGNAL AS
SELECT doc_id, patient_id, encounter_id,
       signal:response:adverse_event::STRING      AS adverse_event,
       signal:response:barrier_to_care::STRING    AS barrier_to_care,
       TRY_TO_NUMBER(signal:response:followup_days::STRING) AS followup_days,
       signal:response:followup_specialty::STRING AS followup_specialty,
       IFF(UPPER(COALESCE(signal:response:barrier_to_care::STRING,'NONE'))
             NOT IN ('NONE','NO BARRIERS IDENTIFIED',''), TRUE, FALSE) AS has_barrier,
       IFF(UPPER(COALESCE(signal:response:adverse_event::STRING,'NONE'))
             NOT LIKE 'NO ADVERSE%' AND UPPER(COALESCE(signal:response:adverse_event::STRING,'NONE')) <> 'NONE',
           TRUE, FALSE) AS has_adverse_event
FROM DOC_SAFETY_SIGNAL;

SELECT doc_type, COUNT(DISTINCT doc_id) AS docs, COUNT(*) AS chunks
FROM DOC_CHUNK GROUP BY 1 ORDER BY 2 DESC;
