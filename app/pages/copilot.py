"""Copilot page — ask questions with cited answers."""
import streamlit as st
from shared import get_session, ask_agent, unpack

session = get_session()

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
            resp = ask_agent(session, question)
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
                    st.info("No document evidence returned. For a policy question, that itself "
                            "is the finding -- the corpus has nothing to support an answer.")
            with e2:
                if sqls:
                    for s in sqls:
                        st.code(s, language="sql")
                else:
                    st.caption("No SQL generated -- this answer came from document retrieval only.")
            with e3:
                st.json(resp["raw"])

            if tools:
                st.caption("Tool trace: " + " -> ".join(tools))
        except Exception as exc:
            st.error(f"Agent call failed: {exc}")
            st.caption("If this is the first run, the Cortex Search services may still be indexing.")
