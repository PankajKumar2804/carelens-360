"""Trust & Evidence page — DQ, grounding, governance posture."""
import pandas as pd
import streamlit as st
from shared import get_session, q

session = get_session()

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
                      FROM CARELENS.GOLD.RISK_READMISSION GROUP BY 1
                      ORDER BY avg_lace DESC""")

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
        st.dataframe(sc, use_container_width=True, hide_index=True) if not sc.empty else st.caption(
            "No answers logged yet. Ask something on the Copilot page.")
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
