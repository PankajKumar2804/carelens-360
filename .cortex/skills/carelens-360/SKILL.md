---
name: carelens-360
description: Build, extend and operate the CareLens 360 patient/member 360 and clinical-regulatory document copilot on Snowflake. Use for any work on the CARELENS database, its semantic view, Cortex Search services, the CARELENS_COPILOT agent, or its evidence and governance layers.
tools:
  - sql_execute
  - snowflake_sql_execute
  - snowflake_object_search
  - bash
  - read
  - write
  - edit
---

# When to Use

Invoke this skill when the user asks to:

- Add or change a clinical, claims or document entity in the `CARELENS` database
- Extend `CARELENS.AI.PATIENT_360_SV` with new facts, dimensions, metrics or verified queries
- Add a risk rule, care-gap rule, or safety-signal extraction
- Ingest a new document class (payer policy, drug label, regulatory bulletin, guideline)
- Modify the `CARELENS.AI.CARELENS_COPILOT` specification or its tool routing
- Debug a copilot answer that is wrong, uncited, or slow
- Run the golden-question evaluation and report grounding scores

# Non-Negotiable Rules For This Project

1. **Synthetic data only.** Never write, load, request or generate data describing a real person.
   Never remove the `SYNTHETIC_DATA_FLAG` tag. If asked to load an external dataset, stop and ask
   whether it is fully synthetic before running anything.
2. **No opaque predictions.** Any risk output must be an additive, inspectable rule set stored
   alongside a `score_explanation` and a `methodology_citation`. Do not introduce an ML model, a
   `SNOWFLAKE.ML` classifier, or an LLM-generated numeric score as a patient-facing risk value.
   If the user asks for one, explain the constraint and offer a rule-based alternative.
3. **Every answer path must be citable.** A new tool, table or view is only done when its output
   traces through `CARELENS.GOLD.EVIDENCE_LEDGER` to either a document chunk (`doc_id` plus
   `section_heading`) or a semantic-view metric plus filters.
4. **Governance travels with the data.** Any new table with patient-level columns gets the
   sensitivity tags, the relevant masking policies, and the `RAP_CLINIC_PANEL` row access policy
   before it is exposed to the agent.
5. **No clinical instruction.** Frame findings as "the documented policy requires X; the record
   shows Y". Never phrase output as a treatment directive.

# Project Map

| Layer | Object | Purpose |
|---|---|---|
| RAW | `STRUCTURED_STAGE`, `DOC_STAGE` | Landing stages for synthetic CSV and documents |
| CURATED | `DIM_PATIENT`, `FACT_*`, `DQ_CHECKS` | Conformed entities and quality gates |
| CURATED | `DOC_METADATA`, `DOC_CHUNK`, `V_DOC_SAFETY_SIGNAL` | Parsed, chunked, mined document corpus |
| GOLD | `PATIENT_360`, `MEMBER_360` | The unified 360 record |
| GOLD | `RISK_READMISSION`, `CARE_GAP`, `EVIDENCE_LEDGER` | Transparent risk, deterministic gaps, citations |
| AI | `PATIENT_360_SV` | Governed semantic view for Cortex Analyst |
| AI | `CLINICAL_NOTE_SEARCH`, `REGULATORY_DOC_SEARCH`, `PATIENT_LOOKUP_SEARCH` | Retrieval |
| AI | `CARELENS_COPILOT`, `GET_EVIDENCE_PACK` | The agent and its audit tool |
| GOVERNANCE | masking / row-access policies, `COPILOT_AUDIT_LOG` | Persona access and answer audit |
| EVAL | `GOLDEN_QUESTIONS`, `V_EVAL_SUMMARY` | Grounding and tool-routing evaluation |

Run order: `sql/00_setup.sql` → `01_load_structured.sql` → `02_documents.sql` →
`03_gold_360.sql` → `04_semantic_view.sql` → `05_search_and_agent.sql` →
`06_governance.sql` → `07_eval.sql`.

# Instructions

## Adding a structured entity
1. Add the raw DDL and `COPY INTO` to `sql/01_load_structured.sql`. Never hand-insert rows.
2. Add the conformed `FACT_*` or `DIM_*` object in `CURATED`.
3. Add at least one `DQ_CHECKS` row covering its key integrity risk.
4. Roll it into `PATIENT_360` only through a `V_PATIENT_*` view, so the 360 stays one row per patient.
5. Register it in `PATIENT_360_SV` with `TABLES`, a `RELATIONSHIPS` entry keyed on `patient_id`,
   then `FACTS`, `DIMENSIONS`, `METRICS` — in that clause order, which Snowflake enforces.
6. Apply tags and policies from `sql/06_governance.sql`.
7. Add a verified query demonstrating the new metric.

## Adding a document class
1. Stage the file under `@CARELENS.RAW.DOC_STAGE`, then `ALTER STAGE ... REFRESH`.
2. For PDF or DOCX use `AI_PARSE_DOCUMENT(TO_FILE(...), {'mode':'LAYOUT'})`. For text or markdown
   use the whole-file format already defined in `02_documents.sql`.
3. Extract metadata regex-first with `AI_EXTRACT` as fallback, so layout changes do not break the
   pipeline and well-formed documents stay cheap.
4. Chunk with `SPLIT_TEXT_RECURSIVE_CHARACTER(text,'markdown',900,150,...)` and always populate
   `section_heading` and `citation_label`. A citation without a section is not acceptable here.
5. Route it to `REGULATORY_DOC_SEARCH` unless it is patient-specific narrative, which goes to
   `CLINICAL_NOTE_SEARCH` with `patient_id` and `encounter_id` as filterable attributes.
6. Add a golden question for the new class, including an adversarial variant it should refuse.

## Adding a risk or care-gap rule
- Express it in SQL as additive integer points or a boolean predicate.
- Emit a `score_explanation` sentence naming every input value used.
- Cite the published basis in `methodology_citation`, or mark it `CARELENS_LOCAL_HEURISTIC` and
  keep it in a separate modifier column so published indices stay undistorted.
- Reference the governing document in `CARE_GAP.governing_document_id`.

## Changing the agent
- Edit the `FROM SPECIFICATION` block in `sql/05_search_and_agent.sql`, then
  `CREATE OR REPLACE AGENT`. Keep the four response sections: Answer, Evidence, Risk basis, Limits.
- Tool descriptions are the routing logic. Be explicit about which question types go where, and
  restate the "call PatientLookup first for named patients" rule.
- After any spec change, re-run the eval and report the grounding and tool-routing deltas.

## Debugging a bad answer
1. `SELECT * FROM CARELENS.GOVERNANCE.COPILOT_AUDIT_LOG ORDER BY asked_at DESC LIMIT 5;`
2. If citations are empty, test retrieval directly with `SNOWFLAKE.CORTEX.SEARCH_PREVIEW`.
3. If a number is wrong, run the generated SQL against `SEMANTIC_VIEW(...)` by hand.
4. If the wrong tool was chosen, sharpen the tool description rather than the system prompt.
5. If it answered from general knowledge, tighten rule 3 in the system instructions and add the
   failing question to the golden set as a `REFUSAL_EXPECTED` case.

# Common Patterns

## Query the semantic view directly
```sql
SELECT * FROM SEMANTIC_VIEW(CARELENS.AI.PATIENT_360_SV
  DIMENSIONS patient.attributed_clinic, risk.risk_band
  METRICS patient.patient_count, risk.avg_lace_index)
ORDER BY patient_count DESC;
```

## Verify retrieval before blaming the model
```sql
SELECT SNOWFLAKE.CORTEX.SEARCH_PREVIEW('CARELENS.AI.REGULATORY_DOC_SEARCH',
  '{"query":"step therapy metformin eGFR","columns":["chunk_text","doc_id","section_heading"],"limit":5}');
```

## Ask the agent from SQL
```sql
SELECT SNOWFLAKE.CORTEX.DATA_AGENT_RUN('CARELENS.AI.CARELENS_COPILOT', $${
  "thread_id":0,"parent_message_id":0,
  "messages":[{"role":"user","content":[{"type":"text","text":"<question>"}]}],
  "stream":false}$$);
```

# Examples

## Example 1
User: `$carelens-360 add immunisation records to the 360 and let me ask about flu-shot gaps`
Assistant: adds `RAW_IMMUNIZATIONS` DDL and `COPY INTO`, a `FACT_IMMUNIZATION` table, a
`V_PATIENT_IMMUNIZATION` rollup, a `FLU_VACCINE_OVERDUE` rule pointing at the quality-measure
document, new `TABLES`/`RELATIONSHIPS`/`METRICS` entries in the semantic view, governance tags, a
verified query, and a golden question — then runs the eval and reports scores.

## Example 2
User: `$carelens-360 the copilot gave me a coverage answer with no document cited`
Assistant: pulls the last audit-log row, runs `SEARCH_PREVIEW` on the same question, reports
whether the failure is retrieval or orchestration, and proposes the narrowest fix.
