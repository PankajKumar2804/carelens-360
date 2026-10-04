"""
CareLens 360 — Streamlit in Snowflake.
Single-file app with sidebar page navigation.
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

# ---------------------------------------------------------------- Design System
st.markdown("""<style>
[data-testid="stAppViewContainer"] { background: #fafbfc; }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stMetric"] {
    background: #ffffff; border: 1px solid #dee2e6;
    border-radius: 8px; padding: 14px 18px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
[data-testid="stMetricLabel"] {
    font-size: 0.78rem !important; color: #5a6c7d !important;
    text-transform: uppercase; letter-spacing: 0.4px;
}
[data-testid="stMetricValue"] {
    font-size: 1.6rem !important; font-weight: 700 !important; color: #1a3353 !important;
}
[data-testid="stSidebar"] { background: #f1f4f7; border-right: 1px solid #dee2e6; }
[data-testid="stBaseButton-primary"] {
    background: linear-gradient(135deg, #0066cc, #0052a3) !important;
    border: none !important; border-radius: 6px !important;
    font-weight: 600 !important; box-shadow: 0 2px 6px rgba(0,102,204,0.25);
}
[data-testid="stDataFrame"] { border: 1px solid #dee2e6; border-radius: 6px; }
.synth-pill {
    display: inline-block; background: #fff3cd; color: #856404;
    font-size: 0.68rem; font-weight: 700; padding: 3px 10px;
    border-radius: 10px; letter-spacing: 0.6px; text-transform: uppercase;
}
.hero-title {
    font-size: 2.6rem; font-weight: 800; margin: 6px 0 0 0;
    letter-spacing: -0.8px; line-height: 1.1; color: #0d2137;
}
.hero-title span {
    background: linear-gradient(135deg, #0066cc 0%, #29b5e8 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.hero-sub { font-size: 1rem; color: #5a6c7d; margin: 4px 0 10px 0; }
.flow-bar {
    display: flex; align-items: center; justify-content: center;
    gap: 0; margin: 8px 0 4px 0; flex-wrap: wrap;
}
.flow-step {
    background: #ffffff; border: 1px solid #cfd8e3; border-radius: 8px;
    padding: 10px 20px; text-align: center; min-width: 110px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}
.flow-step .fs-label { font-weight: 700; font-size: 0.82rem; color: #0d2137; }
.flow-step .fs-sub { font-size: 0.7rem; color: #5a6c7d; margin-top: 2px; }
.flow-arrow { font-size: 1.1rem; color: #0066cc; padding: 0 6px; font-weight: 700; }
</style>""", unsafe_allow_html=True)


# ---------------------------------------------------------------- Helpers
@st.cache_data(ttl=300)
def q(_session, sql: str) -> pd.DataFrame:
    return _session.sql(sql).to_pandas()


def ask_agent(question: str) -> dict:
    body = {
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
                tu = b.get("tool_use") if isinstance(b.get("tool_use"), dict) else {}
                name = tu.get("name") or b.get("name") or b.get("tool_name") or "tool"
                tools.append(name)
                blob = json.dumps(b)
                if "SELECT" in blob.upper():
                    inp = tu.get("input") if isinstance(tu.get("input"), dict) else (b.get("input") if isinstance(b.get("input"), dict) else {})
                    for cand in inp.values():
                        if isinstance(cand, str) and "SELECT" in cand.upper():
                            sqls.append(cand)
            elif btype == "tool_result" or btype == "tool_results":
                tr = b.get("tool_result") if isinstance(b.get("tool_result"), dict) else b
                blob = json.dumps(tr)
                for token in ("doc_id", "citation_label", "source_id"):
                    if token in blob:
                        cites.append(tr)
                        break
                tr_content = tr.get("content")
                if isinstance(tr_content, list):
                    walk(tr_content)
            b_content = b.get("content")
            if isinstance(b_content, list):
                cv = b.get("content_values")
                if isinstance(cv, list):
                    walk(cv)
                walk(b_content)

    walk(blocks)
    if not text:
        debug_str = json.dumps(payload, indent=2) if isinstance(payload, (dict, list)) else str(payload)
        fallback = f"_No text returned. Check the raw response below._\n\n**Debug Payload:**\n```json\n{debug_str}\n```"
        return fallback, tools, sqls, cites
    return "\n\n".join(text), tools, sqls, cites


# ---------------------------------------------------------------- Sidebar nav
with st.sidebar:
    st.markdown("### CareLens 360")
    page = st.radio(
        "Navigate",
        ["Home", "Copilot", "Patient 360", "Clinic Analytics", "Trust & Evidence"],
        label_visibility="collapsed",
    )

# ---------------------------------------------------------------- Welcome hero (always visible)
st.markdown('<span class="synth-pill">Synthetic Data</span>', unsafe_allow_html=True)
st.markdown('<p class="hero-title">Care<span>Lens</span> 360</p>', unsafe_allow_html=True)
st.markdown('<p class="hero-sub">Patient &amp; member 360 + clinical-regulatory document copilot</p>', unsafe_allow_html=True)


# ---------------------------------------------------------------- Home page
if page == "Home":
    try:
        kpi = q(session, """
            SELECT
              (SELECT COUNT(*) FROM CARELENS.GOLD.PATIENT_360)             AS patients,
              (SELECT COUNT(*) FROM CARELENS.CURATED.FACT_ENCOUNTER)       AS encounters,
              (SELECT COUNT(DISTINCT doc_id) FROM CARELENS.CURATED.DOC_METADATA) AS documents,
              (SELECT COUNT(*) FROM CARELENS.GOLD.CARE_GAP)               AS open_gaps,
              (SELECT ROUND(AVG(lace_index),1) FROM CARELENS.GOLD.RISK_READMISSION) AS avg_lace
        """).iloc[0]
        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Patients", f"{int(kpi['PATIENTS']):,}")
        k2.metric("Encounters", f"{int(kpi['ENCOUNTERS']):,}")
        k3.metric("Documents", f"{int(kpi['DOCUMENTS']):,}")
        k4.metric("Care Gaps", f"{int(kpi['OPEN_GAPS']):,}")
        k5.metric("Avg LACE", f"{kpi['AVG_LACE']}")
    except Exception:
        pass

    st.divider()
    st.markdown("""
    **How it works**: CareLens 360 acts as an AI assistant for care managers. It sits downstream of the Electronic Health Record (EHR) and Payer systems, aggregating patient visits, clinical notes, labs, and claims into a unified 360° view. The diagram below shows how data moves from raw ingestion to the AI Copilot.
    """)
    
    flow_html = '<div class="flow-bar">'
    for i, (label, sub) in enumerate([
        ("RAW", "Ingest"), ("CURATED", "Conform + QA"), ("GOLD", "360 + Risk + Gaps"),
        ("AI", "Analyst + Search + Agent"), ("GOVERNANCE", "Masking + RAP + Eval"),
    ]):
        if i > 0:
            flow_html += '<span class="flow-arrow">&#x2192;</span>'
        flow_html += f'<div class="flow-step"><div class="fs-label">{label}</div><div class="fs-sub">{sub}</div></div>'
    flow_html += '</div>'
    st.markdown(flow_html, unsafe_allow_html=True)


# ---------------------------------------------------------------- Copilot
elif page == "Copilot":
    st.subheader("Copilot")
    presets = {
        "-- pick one or type your own --": "",
        "Risk band distribution": "How many patients fall into each readmission risk band, and what is the average LACE index in each?",
        "Why is this patient high risk?": "Why is the highest-risk patient at FVMG-NORTH flagged as high risk? Show the component breakdown.",
        "Patient summary (hybrid)": "Give me a clinical summary of the patient who was admitted most recently, including their LACE risk score and open care gaps.",
        "Clinic comparison": "Compare the average LACE index and total number of open care gaps between FVMG-NORTH and FVMG-SOUTH clinics.",
        "ARNI coverage criteria": "What are the coverage criteria for sacubitril/valsartan, and how long do I have to appeal a denial?",
        "Heart failure therapy gap (hybrid)": "Which heart-failure patients have no ARNI, MRA or SGLT2 inhibitor on file? For each, give the readmission risk with its component breakdown, and quote the prior-authorisation criteria they would need to satisfy, citing document and section.",
        "SGLT2 step therapy (hybrid)": "What step therapy is required before an SGLT2 inhibitor is approved, and how many of our diabetic patients would currently fail it?",
        "High utilization patients": "Which patients have had more than 3 inpatient encounters in the last year, and what were their primary diagnoses?",
        "Quarterly reporting duties": "What does the readmissions bulletin require us to submit each quarter, and what gets rejected?",
        "Out-of-scope (should decline)": "What is the recommended warfarin dose for atrial fibrillation?",
    }
    choice = st.selectbox("Example questions", list(presets.keys()))
    question = st.text_area("Question", value=presets[choice], height=90,
                            placeholder="e.g. Which CKD patients are eligible for an SGLT2 inhibitor but not on one?")

    if st.button("Ask CareLens", type="primary", disabled=not question.strip()):
        with st.spinner("Retrieving evidence and composing a cited answer..."):
            try:
                resp = ask_agent(question)
                answer, tools, sqls, cites = unpack(resp)
                st.markdown("### Answer")
                st.markdown(answer)

                c1, c2, c3 = st.columns(3)
                c1.metric("Tools used", len(tools))
                c2.metric("Evidence blocks", len(cites))
                c3.metric("Latency", f"{resp['latency_ms']} ms")

                st.divider()
                e1, e2, e3 = st.tabs(["Evidence", "Generated SQL", "Raw trace"])
                with e1:
                    if cites:
                        for i, c in enumerate(cites, 1):
                            with st.expander(f"Evidence block {i}"):
                                st.json(c)
                    else:
                        st.info("No document evidence returned.")
                with e2:
                    if sqls:
                        for s in sqls:
                            st.code(s, language="sql")
                    else:
                        st.caption("No SQL generated -- document retrieval only.")
                with e3:
                    st.json(resp["raw"])

                if tools:
                    st.caption("Tool trace: " + " -> ".join(tools))
            except Exception as exc:
                st.error(f"Agent call failed: {exc}")


# ---------------------------------------------------------------- Patient 360
elif page == "Patient 360":
    st.subheader("Patient 360")
    try:
        roster = q(session, """SELECT r.patient_id, p.full_name, r.risk_band, r.lace_index,
                             r.carelens_adjusted_score, r.attributed_clinic
                      FROM CARELENS.GOLD.RISK_READMISSION r
                      JOIN CARELENS.GOLD.PATIENT_360 p USING (patient_id)
                      ORDER BY r.carelens_adjusted_score DESC, r.lace_index DESC LIMIT 60""")
        labels = [f"{r.PATIENT_ID} . {r.FULL_NAME} . {r.RISK_BAND} (LACE {r.LACE_INDEX})"
                  for r in roster.itertuples()]
        pick = st.selectbox("Patient (highest adjusted risk first)", labels)
        pid = pick.split(" . ")[0]

        prof = q(session, f"SELECT * FROM CARELENS.GOLD.PATIENT_360 WHERE patient_id = '{pid}'")
        risk = q(session, f"SELECT * FROM CARELENS.GOLD.RISK_READMISSION WHERE patient_id = '{pid}'")
        if not prof.empty:
            k0 = risk.iloc[0]
            a, b, c, d = st.columns(4)
            a.metric("Risk band", k0["RISK_BAND"])
            b.metric("LACE index", int(k0["LACE_INDEX"]))
            c.metric("Adjusted score", int(k0["CARELENS_ADJUSTED_SCORE"]))
            d.metric("Open gaps", int(q(session, f"SELECT COUNT(*) n FROM CARELENS.GOLD.CARE_GAP WHERE patient_id='{pid}'").iloc[0]["N"]))

            st.info(f"**Why this score:** {k0['SCORE_EXPLANATION']}")
            st.caption(f"Methodology: {k0['METHODOLOGY_CITATION']}")

            st.divider()
            st.markdown("**Score components**")
            st.dataframe(pd.DataFrame({
                "Component": ["L -- length of stay", "A -- acuity of admission",
                              "C -- comorbidity (Charlson)", "E -- ED visits, prior 6 months",
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

            st.divider()
            g1, g2 = st.columns(2)
            with g1:
                st.markdown("**Open care gaps**")
                gaps = q(session, f"SELECT gap_type, gap_detail, governing_document_id FROM CARELENS.GOLD.CARE_GAP WHERE patient_id='{pid}'")
                if gaps.empty:
                    st.success("No open care gaps.")
                else:
                    for _, gap in gaps.iterrows():
                        with st.container(border=True):
                            st.error(f"**{gap['GAP_TYPE']}**: {gap['GAP_DETAIL']}")
                            st.caption(f"Source: {gap['GOVERNING_DOCUMENT_ID']}")
            with g2:
                st.markdown("**Active medications**")
                st.dataframe(q(session, f"""SELECT medication_name, drug_class, adherence_pdc, days_supply
                                   FROM CARELENS.CURATED.FACT_MEDICATION
                                   WHERE patient_id='{pid}' AND active_flag=1"""),
                              use_container_width=True, hide_index=True)

            st.divider()
            st.markdown("**Recent labs**")
            labs = q(session, f"""SELECT collected_date, test_name, result_value, unit,
                                      ref_low, ref_high, abnormal_flag
                               FROM CARELENS.CURATED.FACT_LAB WHERE patient_id='{pid}'
                               ORDER BY collected_date DESC LIMIT 12""")
            if not labs.empty:
                labs['COLLECTED_DATE'] = pd.to_datetime(labs['COLLECTED_DATE'])
                pivot_labs = labs.pivot_table(index='COLLECTED_DATE', columns='TEST_NAME', values='RESULT_VALUE')
                st.line_chart(pivot_labs)
                with st.expander("Raw lab data"):
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
elif page == "Clinic Analytics":
    st.subheader("Clinic Analytics")
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

        st.divider()
        st.markdown("### Top Clinics by Open Care Gaps")
        clinic_gaps = q(session, """SELECT p.attributed_clinic, COUNT(g.gap_type) as total_open_gaps
                           FROM CARELENS.GOLD.CARE_GAP g
                           JOIN CARELENS.GOLD.PATIENT_360 p USING (patient_id)
                           GROUP BY 1 ORDER BY total_open_gaps DESC""")
        st.bar_chart(clinic_gaps.set_index('ATTRIBUTED_CLINIC'))
    except Exception as exc:
        st.error(f"Could not load clinic analytics: {exc}")


# ---------------------------------------------------------------- Trust & Evidence
elif page == "Trust & Evidence":
    st.subheader("Trust & Evidence")
    try:
        counts = q(session, """SELECT 'Patients' AS object, COUNT(*) AS n FROM CARELENS.GOLD.PATIENT_360
                      UNION ALL SELECT 'Encounters', COUNT(*) FROM CARELENS.CURATED.FACT_ENCOUNTER
                      UNION ALL SELECT 'Claims', COUNT(*) FROM CARELENS.CURATED.FACT_CLAIM
                      UNION ALL SELECT 'Documents', COUNT(DISTINCT doc_id) FROM CARELENS.CURATED.DOC_METADATA
                      UNION ALL SELECT 'Document chunks', COUNT(*) FROM CARELENS.CURATED.DOC_CHUNK""")
        cols = st.columns(len(counts))
        for col, row in zip(cols, counts.itertuples()):
            col.metric(row.OBJECT, f"{row.N:,}")

        st.markdown("**Data quality gates** -- zero failing rows is the release condition")
        dq = q(session, "SELECT * FROM CARELENS.CURATED.DQ_CHECKS ORDER BY failing_rows DESC")
        st.dataframe(dq, use_container_width=True, hide_index=True)
        if dq["FAILING_ROWS"].sum() == 0:
            st.success("All quality gates pass.")
        else:
            st.error("One or more gates failed. Fix before demoing.")

        st.divider()
        st.markdown("**Risk band distribution**")
        risk_dist = q(session, """SELECT risk_band, COUNT(*) AS patients,
                                 ROUND(AVG(lace_index),2) AS avg_lace,
                                 ROUND(AVG(carelens_adjusted_score),2) AS avg_adjusted
                          FROM CARELENS.GOLD.RISK_READMISSION GROUP BY 1 ORDER BY avg_lace DESC""")
        rc1, rc2 = st.columns([2, 1])
        with rc1:
            st.bar_chart(risk_dist.set_index('RISK_BAND')['PATIENTS'])
        with rc2:
            st.dataframe(risk_dist, use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("**Care gaps by governing document**")
        st.dataframe(q(session, """SELECT governing_document_id, gap_type, COUNT(*) AS open_gaps
                          FROM CARELENS.GOLD.CARE_GAP GROUP BY 1,2 ORDER BY 3 DESC"""),
                     use_container_width=True, hide_index=True)

        st.markdown("**Grounding scorecard**")
        try:
            sc = q(session, "SELECT * FROM CARELENS.GOVERNANCE.V_GROUNDING_SCORECARD LIMIT 14")
            if not sc.empty:
                st.dataframe(sc, use_container_width=True, hide_index=True)
            else:
                st.caption("No answers logged yet.")
        except Exception:
            st.caption("Audit log not yet populated.")

        st.divider()
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
