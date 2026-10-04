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

/* ---- Card strip (horizontal scroll-snap) ---- */
.card-strip {
    display: flex; gap: 14px; overflow-x: auto; padding: 8px 2px 14px 2px;
    scroll-snap-type: x mandatory; -webkit-overflow-scrolling: touch;
    scrollbar-width: thin;
}
.card-strip::-webkit-scrollbar { height: 6px; }
.card-strip::-webkit-scrollbar-thumb { background: #c1c9d2; border-radius: 3px; }
.snap-card {
    scroll-snap-align: start; flex: 0 0 220px; min-height: 100px;
    border-radius: 10px; padding: 16px 18px; position: relative;
    box-shadow: 0 2px 8px rgba(0,0,0,0.07); transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.snap-card:hover { transform: translateY(-3px); box-shadow: 0 6px 18px rgba(0,0,0,0.12); }
.snap-card .sc-num { font-size: 1.8rem; font-weight: 800; line-height: 1; }
.snap-card .sc-label { font-size: 0.78rem; color: inherit; opacity: 0.85; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.3px; }
.snap-card .sc-detail { font-size: 0.82rem; margin-top: 8px; opacity: 0.9; }
.sc-red { background: linear-gradient(135deg, #fee2e2, #fecaca); color: #991b1b; border: 1px solid #fca5a5; }
.sc-amber { background: linear-gradient(135deg, #fef3c7, #fde68a); color: #92400e; border: 1px solid #fcd34d; }
.sc-green { background: linear-gradient(135deg, #d1fae5, #a7f3d0); color: #065f46; border: 1px solid #6ee7b7; }
.sc-blue { background: linear-gradient(135deg, #dbeafe, #bfdbfe); color: #1e40af; border: 1px solid #93c5fd; }

/* ---- Quick-action tiles ---- */
.action-tile {
    background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px;
    padding: 22px 16px; text-align: center; cursor: pointer;
    transition: all 0.18s ease; box-shadow: 0 1px 4px rgba(0,0,0,0.04);
    min-height: 130px; display: flex; flex-direction: column; align-items: center; justify-content: center;
}
.action-tile:hover { border-color: #0066cc; box-shadow: 0 4px 16px rgba(0,102,204,0.15); transform: translateY(-2px); }
.action-tile .at-icon { font-size: 2rem; margin-bottom: 6px; }
.action-tile .at-title { font-weight: 700; font-size: 0.95rem; color: #0d2137; }
.action-tile .at-stat { font-size: 0.78rem; color: #5a6c7d; margin-top: 4px; }

/* ---- Mini patient table ---- */
.mini-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
.mini-table th { text-align: left; padding: 8px 12px; background: #f1f5f9; color: #475569; font-weight: 600; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.3px; border-bottom: 2px solid #e2e8f0; }
.mini-table td { padding: 10px 12px; border-bottom: 1px solid #f1f5f9; color: #1e293b; }
.mini-table tr:hover td { background: #f8fafc; }
.risk-badge { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 0.72rem; font-weight: 700; text-transform: uppercase; }
.rb-high { background: #fee2e2; color: #991b1b; }
.rb-medium { background: #fef3c7; color: #92400e; }
.rb-low { background: #d1fae5; color: #065f46; }
</style>""", unsafe_allow_html=True)


# ---------------------------------------------------------------- Helpers
@st.cache_data(ttl=300)
def q(_session, sql: str) -> pd.DataFrame:
    return _session.sql(sql).to_pandas()


def safe_int(v, default=0):
    try:
        return int(float(str(v))) if v is not None else default
    except (ValueError, TypeError):
        return default

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
    """Pull text, tool calls, generated SQL and citations out of the agent response."""
    text, tools, sqls, cites = [], [], [], []
    payload = resp.get("raw", resp)

    # Handle double-encoded JSON strings
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            return payload, [], [], []

    # Surface agent-level errors
    if isinstance(payload, dict):
        if payload.get("status") == "failed" or payload.get("error"):
            err = payload.get("error", payload.get("message", "Agent returned an error."))
            return f"**Agent error:** {err}", [], [], []

    # Collect top-level content blocks
    blocks = []
    if isinstance(payload, dict):
        for key in ("content", "messages", "response"):
            v = payload.get(key)
            if isinstance(v, list):
                blocks.extend(v)
        # If messages is a list of message objects, dig into each one's content
        msgs = payload.get("messages")
        if isinstance(msgs, list):
            for m in msgs:
                if isinstance(m, dict) and isinstance(m.get("content"), list):
                    blocks.extend(m["content"])
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
                tu = b.get("tool_use") if isinstance(b.get("tool_use"), dict) else b
                name = tu.get("name") or b.get("name") or b.get("tool_name") or "tool"
                tools.append(name)
                blob = json.dumps(b)
                if "SELECT" in blob.upper():
                    inp = tu.get("input") if isinstance(tu.get("input"), dict) else (b.get("input") if isinstance(b.get("input"), dict) else {})
                    for cand in inp.values():
                        if isinstance(cand, str) and "SELECT" in cand.upper():
                            sqls.append(cand)
            elif btype in ("tool_result", "tool_results"):
                tr = b.get("tool_result") if isinstance(b.get("tool_result"), dict) else b
                blob = json.dumps(tr)
                for token in ("doc_id", "citation_label", "source_id"):
                    if token in blob:
                        cites.append(tr)
                        break
                # Walk into tool_result content for nested text/evidence
                tr_content = tr.get("content")
                if isinstance(tr_content, list):
                    walk(tr_content)
            # Also check for SQL in tool_result json blocks
            if btype == "json" or (isinstance(b.get("json"), dict)):
                j = b.get("json", b)
                if isinstance(j, dict) and j.get("sql"):
                    sqls.append(j["sql"])

            # Recurse into any nested content arrays
            b_content = b.get("content")
            if isinstance(b_content, list):
                walk(b_content)

    walk(blocks)

    # Fallback: if we still have no text, look for any string deeply in the payload
    if not text and isinstance(payload, dict):
        raw_str = json.dumps(payload)
        if "text" in raw_str and len(raw_str) > 200:
            return "_Could not parse the agent response. Check the Raw trace tab for the full output._", tools, sqls, cites

    return "\n\n".join(text) or "_No text returned. Check the raw response below._", tools, sqls, cites


# ---------------------------------------------------------------- Navigation helpers
PAGES = ["Home", "Copilot", "Patient 360", "Clinic Analytics", "Trust & Evidence"]

def go(target: str):
    st.session_state["page"] = target

# ---------------------------------------------------------------- Sidebar nav
with st.sidebar:
    st.markdown("### CareLens 360")
    idx = PAGES.index(st.session_state.get("page", "Home")) if st.session_state.get("page") in PAGES else 0
    page = st.radio(
        "Navigate", PAGES, index=idx, label_visibility="collapsed", key="nav_radio",
    )
    if page != st.session_state.get("page", "Home"):
        st.session_state["page"] = page
    page = st.session_state.get("page", "Home")

# ---------------------------------------------------------------- Welcome hero (always visible)
st.markdown('<span class="synth-pill">Synthetic Data</span>', unsafe_allow_html=True)
st.markdown('<p class="hero-title">Care<span>Lens</span> 360</p>', unsafe_allow_html=True)
st.markdown('<p class="hero-sub">Patient &amp; member 360 + clinical-regulatory document copilot</p>', unsafe_allow_html=True)


# ---------------------------------------------------------------- Home page
if page == "Home":
    try:
        # ---- Fetch data for dashboard ----
        kpi = q(session, """
            SELECT
              (SELECT COUNT(*) FROM CARELENS.GOLD.PATIENT_360)             AS patients,
              (SELECT COUNT(*) FROM CARELENS.CURATED.FACT_ENCOUNTER)       AS encounters,
              (SELECT COUNT(DISTINCT doc_id) FROM CARELENS.CURATED.DOC_METADATA) AS documents,
              (SELECT COUNT(*) FROM CARELENS.GOLD.CARE_GAP)               AS open_gaps,
              (SELECT ROUND(AVG(lace_index),1) FROM CARELENS.GOLD.RISK_READMISSION) AS avg_lace
        """).iloc[0]

        high_risk = q(session, """
            SELECT r.patient_id, p.full_name, r.risk_band, r.lace_index,
                   r.carelens_adjusted_score, r.attributed_clinic
            FROM CARELENS.GOLD.RISK_READMISSION r
            JOIN CARELENS.GOLD.PATIENT_360 p USING (patient_id)
            WHERE r.risk_band = 'HIGH'
            ORDER BY r.carelens_adjusted_score DESC LIMIT 5
        """)

        gap_summary = q(session, """
            SELECT gap_type, COUNT(*) AS cnt
            FROM CARELENS.GOLD.CARE_GAP GROUP BY 1 ORDER BY cnt DESC
        """)

        dq_fails = 0
        try:
            dq_fails = safe_int(q(session, "SELECT SUM(failing_rows) n FROM CARELENS.CURATED.DQ_CHECKS").iloc[0]["N"])
        except Exception:
            pass

        # ---- Attention strip (scrollable cards) ----
        st.markdown("#### Needs Your Attention")
        cards_html = '<div class="card-strip">'

        n_high = len(high_risk)
        if n_high > 0:
            cards_html += f'''<div class="snap-card sc-red">
                <div class="sc-num">{n_high}</div>
                <div class="sc-label">High-Risk Patients</div>
                <div class="sc-detail">Highest LACE: {safe_int(high_risk.iloc[0]["LACE_INDEX"])}</div>
            </div>'''

        n_gaps = safe_int(kpi["OPEN_GAPS"])
        gap_color = "sc-red" if n_gaps > 20 else "sc-amber" if n_gaps > 0 else "sc-green"
        cards_html += f'''<div class="snap-card {gap_color}">
            <div class="sc-num">{n_gaps}</div>
            <div class="sc-label">Open Care Gaps</div>
            <div class="sc-detail">{len(gap_summary)} gap types active</div>
        </div>'''

        if dq_fails > 0:
            cards_html += f'''<div class="snap-card sc-red">
                <div class="sc-num">{dq_fails}</div>
                <div class="sc-label">DQ Failing Rows</div>
                <div class="sc-detail">Fix before demoing</div>
            </div>'''
        else:
            cards_html += '''<div class="snap-card sc-green">
                <div class="sc-num">0</div>
                <div class="sc-label">DQ Failures</div>
                <div class="sc-detail">All gates pass</div>
            </div>'''

        cards_html += f'''<div class="snap-card sc-blue">
            <div class="sc-num">{safe_int(kpi["PATIENTS"]):,}</div>
            <div class="sc-label">Total Patients</div>
            <div class="sc-detail">{safe_int(kpi["ENCOUNTERS"]):,} encounters</div>
        </div>'''

        cards_html += f'''<div class="snap-card sc-blue">
            <div class="sc-num">{safe_int(kpi["DOCUMENTS"]):,}</div>
            <div class="sc-label">Documents Indexed</div>
            <div class="sc-detail">Avg LACE: {kpi["AVG_LACE"]}</div>
        </div>'''

        cards_html += '</div>'
        st.markdown(cards_html, unsafe_allow_html=True)

        # ---- Quick-action tiles ----
        st.markdown("#### Quick Actions")
        t1, t2, t3, t4 = st.columns(4)
        with t1:
            st.markdown('''<div class="action-tile">
                <div class="at-icon">&#128172;</div>
                <div class="at-title">Ask Copilot</div>
                <div class="at-stat">AI-powered clinical Q&A</div>
            </div>''', unsafe_allow_html=True)
            if st.button("Open Copilot", key="go_copilot", use_container_width=True):
                go("Copilot")
                st.rerun()
        with t2:
            st.markdown(f'''<div class="action-tile">
                <div class="at-icon">&#128100;</div>
                <div class="at-title">Patient Lookup</div>
                <div class="at-stat">{safe_int(kpi["PATIENTS"]):,} patients on file</div>
            </div>''', unsafe_allow_html=True)
            if st.button("Open Patient 360", key="go_patient", use_container_width=True):
                go("Patient 360")
                st.rerun()
        with t3:
            st.markdown(f'''<div class="action-tile">
                <div class="at-icon">&#127973;</div>
                <div class="at-title">Clinic Overview</div>
                <div class="at-stat">Risk scores by clinic</div>
            </div>''', unsafe_allow_html=True)
            if st.button("Open Clinic Analytics", key="go_clinic", use_container_width=True):
                go("Clinic Analytics")
                st.rerun()
        with t4:
            st.markdown(f'''<div class="action-tile">
                <div class="at-icon">&#128203;</div>
                <div class="at-title">Trust & Evidence</div>
                <div class="at-stat">{"All gates pass" if dq_fails == 0 else f"{dq_fails} failures"}</div>
            </div>''', unsafe_allow_html=True)
            if st.button("Open Trust Panel", key="go_trust", use_container_width=True):
                go("Trust & Evidence")
                st.rerun()

        # ---- Top at-risk patients ----
        if not high_risk.empty:
            st.markdown("#### Top At-Risk Patients")
            tbl = '<table class="mini-table"><thead><tr><th>Patient</th><th>Clinic</th><th>Risk</th><th>LACE</th><th>Adjusted Score</th></tr></thead><tbody>'
            for _, r in high_risk.iterrows():
                band = r["RISK_BAND"]
                badge_cls = "rb-high" if band == "HIGH" else ("rb-medium" if band == "MEDIUM" else "rb-low")
                tbl += f'''<tr>
                    <td><strong>{r["PATIENT_ID"]}</strong><br><span style="font-size:0.78rem;color:#64748b">{r["FULL_NAME"]}</span></td>
                    <td>{r["ATTRIBUTED_CLINIC"]}</td>
                    <td><span class="risk-badge {badge_cls}">{band}</span></td>
                    <td><strong>{safe_int(r["LACE_INDEX"])}</strong></td>
                    <td><strong>{safe_int(r["CARELENS_ADJUSTED_SCORE"])}</strong></td>
                </tr>'''
            tbl += '</tbody></table>'
            st.markdown(tbl, unsafe_allow_html=True)

        # ---- Care gap breakdown ----
        if not gap_summary.empty:
            st.markdown("#### Care Gaps by Type")
            chart_data = gap_summary.copy()
            chart_data["CNT"] = pd.to_numeric(chart_data["CNT"], errors="coerce").astype(int)
            st.bar_chart(chart_data.set_index("GAP_TYPE")["CNT"])

    except Exception as exc:
        st.error(f"Could not load dashboard: {exc}")


# ---------------------------------------------------------------- Copilot
elif page == "Copilot":
    st.subheader("Copilot")
    presets = {
        "-- pick one or type your own --": "",
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

                # Show raw trace expanded if parsing found nothing useful
                no_content = (not tools and not cites and "No text" in answer) or "Agent error" in answer
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

                if no_content:
                    st.warning("The agent returned a response but no readable answer was extracted. "
                               "Expand the **Raw trace** tab above to inspect the full response.")

                if tools:
                    st.caption("Tool trace: " + " -> ".join(tools))
            except Exception as exc:
                st.error(f"Agent call failed: {exc}")
                import traceback
                st.code(traceback.format_exc(), language="text")


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
            b.metric("LACE index", safe_int(k0["LACE_INDEX"]))
            c.metric("Adjusted score", safe_int(k0["CARELENS_ADJUSTED_SCORE"]))
            d.metric("Open gaps", safe_int(q(session, f"SELECT COUNT(*) n FROM CARELENS.GOLD.CARE_GAP WHERE patient_id='{pid}'").iloc[0]["N"]))

            st.info(f"**Why this score:** {k0['SCORE_EXPLANATION']}")
            st.caption(f"Methodology: {k0['METHODOLOGY_CITATION']}")

            st.divider()
            st.markdown("**Score components**")
            st.dataframe(pd.DataFrame({
                "Component": ["L -- length of stay", "A -- acuity of admission",
                              "C -- comorbidity (Charlson)", "E -- ED visits, prior 6 months",
                              "Local: adherence", "Local: documented barrier"],
                "Points": [safe_int(k0["L_POINTS"]), safe_int(k0["A_POINTS"]), safe_int(k0["C_POINTS"]),
                           safe_int(k0["E_POINTS"]), safe_int(k0["MOD_ADHERENCE_POINT"]), safe_int(k0["MOD_BARRIER_POINT"])],
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
