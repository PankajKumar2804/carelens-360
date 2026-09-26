---
name: phi-guard
description: Pre-flight safety check for healthcare AI work. Use before loading any dataset, writing any patient-level table, or sharing any output, to confirm the data is fully synthetic and that identifiers are tagged, masked and row-restricted.
tools:
  - sql_execute
  - snowflake_sql_execute
  - bash
  - read
---

# When to Use

- Before any `COPY INTO`, `PUT`, `INSERT`, or external data pull in a healthcare project
- Before exposing a new table or view to a Cortex Agent or Cortex Search service
- Before exporting, screenshotting or publishing any query result
- Whenever a user pastes what looks like clinical text into the conversation

# What This Provides

A blocking checklist plus the SQL to prove each item, so a demo cannot accidentally become a
privacy incident.

# Instructions

## Step 1 — provenance
Refuse to proceed until the source is one of: a local generator script in this repo, a recognised
public synthetic generator, or a file the user explicitly confirms is fully synthetic. If the user
pastes free-text clinical content of unknown origin, do not persist it. Ask first.

## Step 2 — identifier inventory
```sql
SELECT table_schema, table_name, column_name, data_type
FROM CARELENS.INFORMATION_SCHEMA.COLUMNS
WHERE LOWER(column_name) REGEXP '.*(name|dob|birth|ssn|mrn|phone|email|address|zip|postal).*'
ORDER BY 1,2,3;
```
Every returned column needs a `DATA_SENSITIVITY` tag and a masking policy.

## Step 3 — policy coverage proof
```sql
SELECT ref_entity_name, ref_column_name, policy_kind, policy_name
FROM TABLE(CARELENS.INFORMATION_SCHEMA.POLICY_REFERENCES(
  REF_ENTITY_NAME => '<fully.qualified.table>', REF_ENTITY_DOMAIN => 'TABLE'));
```
Fail if any inventoried column has no masking policy, or if a patient-level table has no row
access policy.

## Step 4 — persona spot-check
Re-run the same `SELECT` as each of `CARELENS_CLINICIAN`, `CARELENS_CARE_MGR` and
`CARELENS_ANALYST` and show the three outputs side by side. Names must be full, initialled and
redacted respectively. Clinical narrative must be withheld from the analyst role.

## Step 5 — labelling
Confirm the object carries `SYNTHETIC_DATA_FLAG = 'TRUE'` and that any UI surface or exported
artifact displays a visible synthetic-data banner.

## Output Format

```
PHI-GUARD CHECK — <object>
Provenance ........ PASS/FAIL  <source>
Identifier tags ... PASS/FAIL  <n columns untagged>
Masking ........... PASS/FAIL  <n columns unmasked>
Row access ........ PASS/FAIL  <policy or NONE>
Persona check ..... PASS/FAIL  <what each role saw>
Synthetic label ... PASS/FAIL
VERDICT: SAFE TO PROCEED | BLOCKED — <reason>
```

Never report PASS on an item you did not actually execute a query to verify.
