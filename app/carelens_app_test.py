import streamlit as st
from snowflake.snowpark.context import get_active_session

st.set_page_config(page_title="CareLens 360", layout="wide")
session = get_active_session()

st.title("CareLens 360")
st.caption("Minimal test - confirming deployment works")

try:
    df = session.sql("SELECT COUNT(*) AS n FROM CARELENS.GOLD.PATIENT_360").to_pandas()
    st.metric("Patients", str(df.iloc[0]["N"]))
    st.success("Database connection works!")
except Exception as e:
    st.error("DB error: " + str(e))
