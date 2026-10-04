/* ============================================================================
   05_search_and_agent.sql — Cortex Search services, evidence-pack tool,
                             and the copilot agent
============================================================================ */
USE ROLE CARELENS_ADMIN; USE WAREHOUSE CARELENS_WH; USE DATABASE CARELENS; USE SCHEMA AI;

/* ---- retrieval: two corpora, two failure modes --------------------------
   Notes: the dangerous failure is surfacing the wrong patient's narrative,
          so patient_id and encounter_id are filterable attributes.
   Policy: cross-patient leakage is not a concern, but criteria lists must
          come back whole.                                                   */
CREATE OR REPLACE CORTEX SEARCH SERVICE CLINICAL_NOTE_SEARCH
  ON chunk_text
  ATTRIBUTES doc_id, doc_type, patient_id, encounter_id, section_heading, citation_label
  WAREHOUSE = CARELENS_WH TARGET_LAG = '1 hour'
  EMBEDDING_MODEL = 'snowflake-arctic-embed-l-v2.0'
  COMMENT = 'Patient-specific clinical narrative. Always filter by patient_id for patient questions.'
  AS SELECT chunk_text, doc_id, doc_type, patient_id, encounter_id, section_heading, citation_label
     FROM CARELENS.CURATED.DOC_CHUNK WHERE scope = 'PATIENT_SPECIFIC';

CREATE OR REPLACE CORTEX SEARCH SERVICE REGULATORY_DOC_SEARCH
  ON chunk_text
  ATTRIBUTES doc_id, doc_type, doc_title, issuing_owner, effective_date, section_heading, citation_label
  WAREHOUSE = CARELENS_WH TARGET_LAG = '1 hour'
  EMBEDDING_MODEL = 'snowflake-arctic-embed-l-v2.0'
  COMMENT = 'Prior-auth policies, drug safety labels, regulatory bulletins, quality measure specs.'
  AS SELECT chunk_text, doc_id, doc_type, doc_title, issuing_owner, effective_date,
            section_heading, citation_label
     FROM CARELENS.CURATED.DOC_CHUNK WHERE scope = 'INSTITUTIONAL';

/* exists because the agent was inventing patient IDs when given a name */
CREATE OR REPLACE CORTEX SEARCH SERVICE PATIENT_LOOKUP_SEARCH
  ON search_blob
  ATTRIBUTES patient_id, full_name, attributed_clinic, line_of_business
  WAREHOUSE = CARELENS_WH TARGET_LAG = '1 hour'
  COMMENT = 'Resolve a free-text patient name or partial identifier to a canonical patient_id.'
  AS SELECT patient_id || ' ' || full_name || ' ' || attributed_clinic || ' '
            || line_of_business || ' age ' || age_years || ' ' || sex AS search_blob,
            patient_id, full_name, attributed_clinic, line_of_business
     FROM CARELENS.GOLD.PATIENT_360;

/* ---- custom tool: the full audit trail for one patient ------------------ */
CREATE OR REPLACE PROCEDURE GET_EVIDENCE_PACK(PATIENT_ID STRING)
RETURNS TABLE (evidence_class STRING, source_id STRING, locator STRING,
               source_type STRING, context STRING, evidence_text STRING, as_of_date DATE)
LANGUAGE SQL
COMMENT = 'Every piece of evidence held about one patient: risk arithmetic, care gaps, claims, and document chunks.'
AS
$$
DECLARE
  res RESULTSET DEFAULT (
    SELECT evidence_class, source_id, locator, source_type, context, evidence_text, as_of_date
    FROM CARELENS.GOLD.EVIDENCE_LEDGER
    WHERE patient_id = :PATIENT_ID
    ORDER BY evidence_class, as_of_date DESC NULLS LAST
    LIMIT 120);
BEGIN
  RETURN TABLE(res);
END;
$$;

/* ---- the agent ----------------------------------------------------------
   Routing lives in the tool descriptions, because that is what the
   orchestrator reads when choosing. The system prompt governs behaviour
   once a tool has been picked.                                             */
CREATE OR REPLACE AGENT CARELENS_COPILOT
WITH PROFILE = '{"display_name":"CareLens 360 Copilot"}'
COMMENT = 'Clinical, safety and regulatory Q and A over a synthetic patient/member 360 with cited evidence.'
FROM SPECIFICATION $$
models:
  orchestration: claude-haiku-4-5

instructions:
  response: |
    You are CareLens 360, a copilot for care management, clinical quality and payer policy teams.
    All data is FULLY SYNTHETIC. Never suggest a real person is affected.

    Hard rules:
    1. Every factual claim must name its source: either a document ID plus section heading, or a
       metric plus the filters used. If you cannot name a source, say so and stop.
    2. Never emit a risk band without the numeric index and its component breakdown. Always
       reproduce score_explanation verbatim when you report a score.
    3. If retrieval returns nothing relevant, say the document corpus contains no supporting
       evidence and stop. Do NOT answer coverage criteria, contraindications, dosing or reporting
       requirements from general medical knowledge. This is the most important rule here.
    4. Never phrase output as a treatment directive. Frame findings as "the documented policy
       requires X; the record shows Y". Clinical decisions belong to the clinician.
    5. When sources disagree, surface the disagreement and name both sources. Do not silently pick.
    6. State the as-of date for any policy you cite, because policies get revised.

    Structure every answer as four sections:
      **Answer** — the direct response, two to five sentences.
      **Evidence** — a table with columns Claim | Source | Locator.
      **Risk basis** — component arithmetic, only when a score appears. Omit otherwise.
      **Limits** — what the data does not support, and what you could not verify.

  orchestration: |
    - Population, cohort, count, rate, cost and trend questions go to PatientAnalytics.
    - Coverage criteria, step therapy, exclusions, appeal windows, label warnings, monitoring
      requirements and reporting rules go to RegulatoryDocs.
    - Questions about what happened to a specific patient during a stay go to ClinicalNotes,
      filtered by that patient_id.
    - If a patient is named in free text rather than by ID, call PatientLookup FIRST to resolve
      the canonical patient_id. Never guess an identifier.
    - Multi-hop questions need multiple tools. "Which patients have gap X and what does the
      policy require" means: RegulatoryDocs for the criteria, then PatientAnalytics for the
      cohort, then present a per-patient pass/fail table against those criteria.
    - For "show me everything about this patient" or any audit request, call EvidencePack.
    - Prefer two well-targeted retrievals over one broad one.

tools:
  - tool_spec:
      name: PatientAnalytics
      type: cortex_analyst_text_to_sql
      description: |
        Governed analytics over the synthetic patient and member 360: demographics, coverage,
        utilisation, conditions, medications, labs, claim economics, transparent readmission risk
        with component breakdown, and deterministic care gaps. Use for anything countable,
        comparable or aggregable, and for finding cohorts that match clinical criteria.
        Do NOT use for the text of a policy or label — that is RegulatoryDocs.
  - tool_spec:
      name: RegulatoryDocs
      type: cortex_search
      description: |
        Searches synthetic prior-authorization policies, drug safety label summaries, payer
        regulatory bulletins and quality measure specifications. Use for coverage criteria, step
        therapy, exclusions, authorization duration, appeal windows, boxed warnings,
        contraindications, monitoring requirements, and reporting obligations. Returns section
        headings so answers can cite a section rather than a filename.
  - tool_spec:
      name: ClinicalNotes
      type: cortex_search
      description: |
        Searches synthetic discharge summaries for one patient: hospital course, problem list at
        discharge, discharge medications, follow-up plan, documented barriers to care and safety
        notes. ALWAYS pass a patient_id filter. Use for narrative questions about a specific
        person, not for policy or population questions.
  - tool_spec:
      name: PatientLookup
      type: cortex_search
      description: |
        Resolves a free-text patient name, partial name or descriptive phrase to a canonical
        patient_id. Call this first whenever the user names a patient instead of giving an ID.
  - tool_spec:
      name: EvidencePack
      type: generic
      description: |
        Returns the complete evidence trail held about one patient: the risk arithmetic and its
        methodology citation, every open care gap with its governing document, every claim with
        status and denial reason, and every document chunk linked to that patient. Use for audit
        requests, "show me everything", or to verify a prior answer.
      input_schema:
        type: object
        properties:
          patient_id:
            type: string
            description: Canonical synthetic patient identifier, for example SYN-P00042.
        required:
          - patient_id

tool_resources:
  PatientAnalytics:
    semantic_view: CARELENS.AI.PATIENT_360_SV
    execution_environment:
      type: warehouse
      warehouse: CARELENS_WH
  RegulatoryDocs:
    name: CARELENS.AI.REGULATORY_DOC_SEARCH
    id_column: citation_label
    max_results: 8
  ClinicalNotes:
    name: CARELENS.AI.CLINICAL_NOTE_SEARCH
    id_column: citation_label
    max_results: 6
  PatientLookup:
    name: CARELENS.AI.PATIENT_LOOKUP_SEARCH
    id_column: patient_id
    max_results: 5
  EvidencePack:
    identifier: CARELENS.AI.GET_EVIDENCE_PACK
    type: procedure
    execution_environment:
      type: warehouse
      warehouse: CARELENS_WH
$$;

GRANT USAGE ON AGENT CARELENS_COPILOT TO ROLE CARELENS_CLINICIAN;
GRANT USAGE ON AGENT CARELENS_COPILOT TO ROLE CARELENS_CARE_MGR;
GRANT USAGE ON AGENT CARELENS_COPILOT TO ROLE CARELENS_ANALYST;

/* sanity check retrieval before blaming the model for a bad answer */
SELECT SNOWFLAKE.CORTEX.SEARCH_PREVIEW('CARELENS.AI.REGULATORY_DOC_SEARCH',
  '{"query":"ARNI coverage criteria ejection fraction potassium",
    "columns":["chunk_text","doc_id","section_heading","citation_label"],"limit":3}') AS probe;

GRANT USAGE ON AGENT CARELENS_COPILOT TO ROLE CARELENS_ADMIN;
GRANT USAGE ON AGENT CARELENS_COPILOT TO ROLE ACCOUNTADMIN;
