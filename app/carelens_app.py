"""
CareLens 360 — Streamlit in Snowflake.

Three surfaces:
  Copilot         ask a question, see the answer with its evidence and generated SQL
  Patient 360     one patient, with the risk arithmetic spelled out
  Trust & Evidence  data quality, grounding scorecard, governance posture

All data is synthetic. The banner stays visible on purpose.
"""
import json
import time

import pandas as pd
import streamlit as st
from snowflake.snowpark.context import get_active_session

st.set_page_config(page_title="CareLens 360", layout="wide")
session = get_active_session()

AGENT = "CARELENS.AI.CARELENS_COPILOT"


@st.cache_data(ttl=300)
def q(_session, sql: str) -> pd.DataFrame:
    return _session.sql(sql).to_pandas()


def ask_agent(question: str) -> dict:
    body = {
        "thread_id": 0,
        "parent_message_id": 0,
        "messages": [{"role": "user", "content": [{"type": "text", "text": question}]}],
        "stream": False,
    }
    t0 = time.time()
    body_str = json.dumps(body)
    raw = session.sql(
        f"SELECT SNOWFLAKE.CORTEX.DATA_AGENT_RUN('{AGENT}', $${body_str}$$) AS r"
    ).collect()[0]["R"]
    return {"raw": json.loads(raw) if isinstance(raw, str) else raw,
            "latency_ms": int((time.time() - t0) * 1000)}


def unpack(resp: dict):
    """Pull text, tool calls, generated SQL and citations out of the agent response."""
    text, tools, sqls, cites = [], [], [], []
    payload = resp.get("raw", resp)
    blocks = []
    if isinstance(payload, dict):
        for key in ("content", "messages", "response"):
            v = payload.get(key)
            if isinstance(v, list):
                blocks.extend(v)
    elif isinstance(payload, list):
        blocks = payload

    def walk(items):
        for b in items:
            if not isinstance(b, dict):
                continue
            btype = b.get("type")
            if btype == "text" and b.get("text"):
                text.append(b["text"])
            elif btype == "tool_use":
                tools.append(b.get("name") or b.get("tool_name") or "tool")
                blob = json.dumps(b)
                if "SELECT" in blob.upper():
                    for cand in (b.get("input") or {}).values():
                        if isinstance(cand, str) and "SELECT" in cand.upper():
                            sqls.append(cand)
            elif btype == "tool_results":
                blob = json.dumps(b)
                for token in ("doc_id", "citation_label", "source_id"):
                    if token in blob:
                        cites.append(b)
                        break
            if isinstance(b.get("content"), list):
                walk(b["content"])

    walk(blocks)
    return "\n\n".join(text) or "_No text returned. Check the raw response below._", tools, sqls, cites


st.warning(
    "**Synthetic data only.** Every patient, encounter, claim, note and policy in this "
    "application was machine-generated. Nothing here describes a real person."
)
st.title("CareLens 360")
st.caption("Patient & member 360 with a clinical and regulatory document copilot")

tab_copilot, tab_patient, tab_clinic, tab_trust = st.tabs(["Copilot", "Patient 360", "Clinic Analytics", "Trust & Evidence"])

# ---------------------------------------------------------------- Copilot
with tab_copilot:
    st.subheader("Ask a question")
    presets = {
        "— pick one or type your own —": "",
        "Risk band distribution": "How many patients fall into each readmission risk band, and what is the average LACE index in each?",
        "Why is this patient high risk?": "Why is the highest-risk patient at FVMG-NORTH flagged as high risk? Show the component breakdown.",
        "ARNI coverage criteria": "What are the coverage criteria for sacubitril/valsartan, and how long do I have to appeal a denial?",
        "Heart failure therapy gap (hybrid)": "Which heart-failure patients have no ARNI, MRA or SGLT2 inhibitor on file? For each, give the readmission risk with its component breakdown, and quote the prior-authorisation criteria they would need to satisfy, citing document and section.",
        "SGLT2 step therapy (hybrid)": "What step therapy is required before an SGLT2 inhibitor is approved, and how many of our diabetic patients would currently fail it?",
        "Quarterly reporting duties": "What does the readmissions bulletin require us to submit each quarter, and what gets rejected?",
        "Out-of-scope (should decline)": "What is the recommended warfarin dose for atrial fibrillation?",
    }
    choice = st.selectbox("Example questions", list(presets.keys()))
    question = st.text_area("Question", value=presets[choice], height=90,
                            placeholder="e.g. Which CKD patients are eligible for an SGLT2 inhibitor but not on one?")

    if st.button("Ask CareLens", type="primary", disabled=not question.strip()):
        with st.spinner("Retrieving evidence and composing a cited answer…"):
            try:
                resp = ask_agent(question)
                answer, tools, sqls, cites = unpack(resp)
                st.markdown("### Answer")
                st.markdown(answer)

                c1, c2, c3 = st.columns(3)
                c1.metric("Tools used", len(tools))
                c2.metric("Evidence blocks", len(cites))
                c3.metric("Latency", f"{resp['latency_ms']} ms")

                e1, e2, e3 = st.tabs(["Evidence", "Generated SQL", "Raw trace"])
                with e1:
                    if cites:
                        for i, c in enumerate(cites, 1):
                            with st.expander(f"Evidence block {i}"):
                                st.json(c)
                    else:
                        st.info("No document evidence returned. For a policy question, that itself "
                                "is the finding — the corpus has nothing to support an answer.")
                with e2:
                    if sqls:
                        for s in sqls:
                            st.code(s, language="sql")
                    else:
                        st.caption("No SQL generated — this answer came from document retrieval only.")
                with e3:
                    st.json(resp["raw"])

                if tools:
                    st.caption("Tool trace: " + " → ".join(tools))
            except Exception as exc:
                st.error(f"Agent call failed: {exc}")
                st.caption("If this is the first run, the Cortex Search services may still be indexing.")

# ---------------------------------------------------------------- Patient 360
with tab_patient:
    st.subheader("One patient, end to end")
    st.caption("Comprehensive medical profile including LACE-derived readmission risk and guideline-driven care gaps.")
    try:
        roster = q(session, """SELECT r.patient_id, p.full_name, r.risk_band, r.lace_index,
                             r.carelens_adjusted_score, r.attributed_clinic
                      FROM CARELENS.GOLD.RISK_READMISSION r
                      JOIN CARELENS.GOLD.PATIENT_360 p USING (patient_id)
                      ORDER BY r.carelens_adjusted_score DESC, r.lace_index DESC LIMIT 60""")
        labels = [f"{r.PATIENT_ID} · {r.FULL_NAME} · {r.RISK_BAND} (LACE {r.LACE_INDEX})"
                  for r in roster.itertuples()]
        pick = st.selectbox("Patient (highest adjusted risk first)", labels)
        pid = pick.split(" · ")[0]

        prof = q(session, f"SELECT * FROM CARELENS.GOLD.PATIENT_360 WHERE patient_id = '{pid}'")
        risk = q(session, f"SELECT * FROM CARELENS.GOLD.RISK_READMISSION WHERE patient_id = '{pid}'")
        if not prof.empty:
            r0, k0 = prof.iloc[0], risk.iloc[0]
            a, b, c, d = st.columns(4)
            a.metric("Risk band", k0["RISK_BAND"], help="Categorical risk stratification for 30-day hospital readmission.")
            b.metric("LACE index", int(k0["LACE_INDEX"]), help="Standardized LACE index scoring: Length of stay, Acuity of admission, Comorbidities, and Emergency department visits.")
            c.metric("Adjusted score", int(k0["CARELENS_ADJUSTED_SCORE"]), help="Composite risk score incorporating baseline LACE index with Social Determinants of Health (SDoH) modifiers.")
            d.metric("Open gaps", int(q(session, f"SELECT COUNT(*) n FROM CARELENS.GOLD.CARE_GAP WHERE patient_id='{pid}'").iloc[0]["N"]), help="Count of active, unresolved clinical care gaps flagged by regulatory guidelines.")

            st.info(f"**Why this score:** {k0['SCORE_EXPLANATION']}")
            st.caption(f"Methodology: {k0['METHODOLOGY_CITATION']}")

            st.markdown("**Score components** — this is the whole model, not a summary of one")
            st.dataframe(pd.DataFrame({
                "Component": ["L — length of stay", "A — acuity of admission",
                              "C — comorbidity (Charlson)", "E — ED visits, prior 6 months",
                              "Local: adherence", "Local: documented barrier"],
                "Points": [int(k0["L_POINTS"]), int(k0["A_POINTS"]), int(k0["C_POINTS"]),
                           int(k0["E_POINTS"]), int(k0["MOD_ADHERENCE_POINT"]), int(k0["MOD_BARRIER_POINT"])],
                "In published LACE": ["yes", "yes", "yes", "yes", "no", "no"],
            }), use_container_width=True, hide_index=True)

            st.markdown("**Profile**")
            st.dataframe(prof[["FULL_NAME", "AGE_YEARS", "SEX", "ATTRIBUTED_CLINIC", "PAYER_NAME",
                               "LINE_OF_BUSINESS", "RISK_PROGRAM", "ACTIVE_CONDITION_COUNT",
                               "ACTIVE_MED_COUNT", "WORST_PDC", "ED_VISITS_6MO",
                               "TOTAL_ALLOWED_AMOUNT"]].T.rename(columns={0: "Value"}),
                         use_container_width=True)

            g1, g2 = st.columns(2)
            with g1:
                st.markdown("**Open care gaps (Actionable)**")
                gaps = q(session, f"SELECT gap_type, gap_detail, governing_document_id FROM CARELENS.GOLD.CARE_GAP WHERE patient_id='{pid}'")
                if gaps.empty:
                    st.success("No open care gaps for this patient.")
                else:
                    for _, gap in gaps.iterrows():
                        with st.container(border=True):
                            st.error(f"**{gap['GAP_TYPE']}**: {gap['GAP_DETAIL']}")
                            st.caption(f"Source: {gap['GOVERNING_DOCUMENT_ID']}")
                            st.button(f"Resolve: {gap['GAP_TYPE']}", key=f"resolve_{gap['GAP_TYPE']}_{pid}", use_container_width=True)
            with g2:
                st.markdown("**Active medications**")
                st.dataframe(q(session, f"""SELECT medication_name, drug_class, adherence_pdc, days_supply
                                   FROM CARELENS.CURATED.FACT_MEDICATION
                                   WHERE patient_id='{pid}' AND active_flag=1"""),
                             use_container_width=True, hide_index=True)

            st.markdown("**Recent labs (Trend)**")
            labs = q(session, f"""SELECT collected_date, test_name, result_value, unit,
                                      ref_low, ref_high, abnormal_flag
                               FROM CARELENS.CURATED.FACT_LAB WHERE patient_id='{pid}'
                               ORDER BY collected_date DESC LIMIT 12""")
            if not labs.empty:
                # Pivot labs to show a line chart of results over time
                labs['COLLECTED_DATE'] = pd.to_datetime(labs['COLLECTED_DATE'])
                pivot_labs = labs.pivot_table(index='COLLECTED_DATE', columns='TEST_NAME', values='RESULT_VALUE')
                st.line_chart(pivot_labs)
                with st.expander("View Raw Lab Data"):
                    st.dataframe(labs, use_container_width=True, hide_index=True)
            else:
                st.caption("No recent labs found.")

            st.markdown("**Linked documents**")
            st.dataframe(q(session, f"""SELECT DISTINCT doc_id, doc_title, doc_type, effective_date
                               FROM CARELENS.CURATED.DOC_CHUNK WHERE patient_id='{pid}'"""),
                         use_container_width=True, hide_index=True)
    except Exception as exc:
        st.error(f"Could not load the patient view: {exc}")

# ---------------------------------------------------------------- Clinic Analytics
with tab_clinic:
    st.subheader("Clinic Population Health & Analytics")
    st.caption("Aggregated population health metrics for resource allocation and risk monitoring across facilities.")
    try:
        st.markdown("### Risk Overview by Clinic")
        clinic_risk = q(session, """SELECT p.attributed_clinic, 
                                  COUNT(r.patient_id) as total_patients,
                                  ROUND(AVG(r.carelens_adjusted_score), 2) as avg_risk_score
                           FROM CARELENS.GOLD.RISK_READMISSION r
                           JOIN CARELENS.GOLD.PATIENT_360 p USING (patient_id)
                           GROUP BY 1 ORDER BY avg_risk_score DESC""")
        
        c1, c2 = st.columns([2, 1])
        with c1:
            st.bar_chart(clinic_risk.set_index('ATTRIBUTED_CLINIC')['AVG_RISK_SCORE'])
        with c2:
            st.dataframe(clinic_risk, use_container_width=True, hide_index=True)

        st.markdown("### Top Clinics by Open Care Gaps")
        clinic_gaps = q(session, """SELECT p.attributed_clinic, COUNT(g.gap_type) as total_open_gaps
                           FROM CARELENS.GOLD.CARE_GAP g
                           JOIN CARELENS.GOLD.PATIENT_360 p USING (patient_id)
                           GROUP BY 1 ORDER BY total_open_gaps DESC""")
        st.bar_chart(clinic_gaps.set_index('ATTRIBUTED_CLINIC'))
    except Exception as exc:
        st.error(f"Could not load clinic analytics: {exc}")

# ---------------------------------------------------------------- Trust
with tab_trust:
    st.subheader("Trust & Evidence")
    st.caption("System observability: Pipeline data quality, AI grounding metrics, and active Role-Based Access Control (RBAC) postures.")
    try:
        counts = q(session, """SELECT 'Patients' AS object, COUNT(*) AS n FROM CARELENS.GOLD.PATIENT_360
                      UNION ALL SELECT 'Encounters', COUNT(*) FROM CARELENS.CURATED.FACT_ENCOUNTER
                      UNION ALL SELECT 'Claims', COUNT(*) FROM CARELENS.CURATED.FACT_CLAIM
                      UNION ALL SELECT 'Documents', COUNT(DISTINCT doc_id) FROM CARELENS.CURATED.DOC_METADATA
                      UNION ALL SELECT 'Document chunks', COUNT(*) FROM CARELENS.CURATED.DOC_CHUNK""")
        cols = st.columns(len(counts))
        for col, row in zip(cols, counts.itertuples()):
            col.metric(row.OBJECT, f"{row.N:,}")

        st.markdown("**Data quality gates** — zero failing rows is the release condition")
        dq = q(session, "SELECT * FROM CARELENS.CURATED.DQ_CHECKS ORDER BY failing_rows DESC")
        st.dataframe(dq, use_container_width=True, hide_index=True)
        if dq["FAILING_ROWS"].sum() == 0:
            st.success("All quality gates pass.")
        else:
            st.error("One or more gates failed. Fix before demoing.")

        st.markdown("**Risk band distribution**")
        risk_dist = q(session, """SELECT risk_band, COUNT(*) AS patients,
                                 ROUND(AVG(lace_index),2) AS avg_lace,
                                 ROUND(AVG(carelens_adjusted_score),2) AS avg_adjusted
                          FROM CARELENS.GOLD.RISK_READMISSION GROUP BY 1
                          ORDER BY avg_lace DESC""")
        
        rc1, rc2 = st.columns([2, 1])
        with rc1:
            st.bar_chart(risk_dist.set_index('RISK_BAND')['PATIENTS'])
        with rc2:
            st.dataframe(risk_dist, use_container_width=True, hide_index=True)

        st.markdown("**Care gaps by governing document**")
        st.dataframe(q(session, """SELECT governing_document_id, gap_type, COUNT(*) AS open_gaps
                          FROM CARELENS.GOLD.CARE_GAP GROUP BY 1,2 ORDER BY 3 DESC"""),
                     use_container_width=True, hide_index=True)

        st.markdown("**Grounding scorecard**")
        try:
            sc = q(session, "SELECT * FROM CARELENS.GOVERNANCE.V_GROUNDING_SCORECARD LIMIT 14")
            st.dataframe(sc, use_container_width=True, hide_index=True) if not sc.empty else st.caption(
                "No answers logged yet. Ask something on the Copilot tab.")
        except Exception:
            st.caption("Audit log not yet populated.")

        st.markdown("**Governance posture**")
        st.dataframe(pd.DataFrame({
            "Role": ["CARELENS_CLINICIAN", "CARELENS_CARE_MGR", "CARELENS_ANALYST"],
            "Names": ["full", "initial + mask", "redacted"],
            "Date of birth": ["full", "year only", "year only"],
            "Postal code": ["full", "first 3", "first 3"],
            "Clinical narrative": ["full", "full", "withheld"],
            "Rows": ["own clinics", "entitled clinics", "all rows, masked columns"],
        }), use_container_width=True, hide_index=True)
        st.caption("Policies evaluate under the caller's role, so the copilot inherits entitlement "
                   "rather than reimplementing it.")
    except Exception as exc:
        st.error(f"Trust panel failed: {exc}")
