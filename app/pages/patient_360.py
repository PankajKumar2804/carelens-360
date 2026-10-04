"""Patient 360 page — single patient deep-dive."""
import pandas as pd
import streamlit as st
from shared import get_session, q

session = get_session()

st.subheader("Patient 360")

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
        a.metric("Risk band", k0["RISK_BAND"])
        b.metric("LACE index", int(k0["LACE_INDEX"]))
        c.metric("Adjusted score", int(k0["CARELENS_ADJUSTED_SCORE"]))
        d.metric("Open gaps", int(q(session, f"SELECT COUNT(*) n FROM CARELENS.GOLD.CARE_GAP WHERE patient_id='{pid}'").iloc[0]["N"]))

        st.info(f"**Why this score:** {k0['SCORE_EXPLANATION']}")
        st.caption(f"Methodology: {k0['METHODOLOGY_CITATION']}")

        st.divider()
        st.markdown("**Score components** -- this is the whole model, not a summary of one")
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
