"""Clinic Analytics page — population health by facility."""
import streamlit as st
from shared import get_session, q

session = get_session()

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
