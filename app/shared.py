"""Shared utilities, constants, and design system for CareLens 360."""
import json
import time

import pandas as pd
import streamlit as st
from snowflake.snowpark.context import get_active_session

AGENT = "CARELENS.AI.CARELENS_COPILOT"


def get_session():
    return get_active_session()


@st.cache_data(ttl=300)
def q(_session, sql: str) -> pd.DataFrame:
    return _session.sql(sql).to_pandas()


def ask_agent(session, question: str) -> dict:
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
    return "\n\n".join(text) or "_No text returned. Check the raw response below._", tools, sqls, cites


def inject_css():
    """Inject the healthcare design system CSS."""
    st.markdown("""<style>
[data-testid="stAppViewContainer"] { background: #fafbfc; }
[data-testid="stHeader"] { background: transparent; }

[data-testid="stMetric"] {
    background: #ffffff;
    border: 1px solid #dee2e6;
    border-radius: 8px;
    padding: 14px 18px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
[data-testid="stMetricLabel"] {
    font-size: 0.78rem !important;
    color: #5a6c7d !important;
    text-transform: uppercase;
    letter-spacing: 0.4px;
}
[data-testid="stMetricValue"] {
    font-size: 1.6rem !important;
    font-weight: 700 !important;
    color: #1a3353 !important;
}

[data-testid="stSidebar"] {
    background: #f1f4f7;
    border-right: 1px solid #dee2e6;
}
[data-testid="stSidebar"] [data-testid="stMarkdown"] p {
    color: #2c3e50;
}

[data-testid="stBaseButton-primary"] {
    background: linear-gradient(135deg, #0066cc, #0052a3) !important;
    border: none !important;
    border-radius: 6px !important;
    font-weight: 600 !important;
    letter-spacing: 0.3px;
    box-shadow: 0 2px 6px rgba(0,102,204,0.25);
    transition: all 0.15s ease;
}
[data-testid="stBaseButton-primary"]:hover {
    box-shadow: 0 4px 12px rgba(0,102,204,0.35) !important;
    transform: translateY(-1px);
}

[data-testid="stDataFrame"] {
    border: 1px solid #dee2e6;
    border-radius: 6px;
}

.synth-pill {
    display: inline-block;
    background: #fff3cd;
    color: #856404;
    font-size: 0.68rem;
    font-weight: 700;
    padding: 3px 10px;
    border-radius: 10px;
    letter-spacing: 0.6px;
    text-transform: uppercase;
}
.hero-title {
    font-size: 2.6rem;
    font-weight: 800;
    margin: 6px 0 0 0;
    letter-spacing: -0.8px;
    line-height: 1.1;
    color: #0d2137;
}
.hero-title span {
    background: linear-gradient(135deg, #0066cc 0%, #29b5e8 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
.hero-sub {
    font-size: 1rem;
    color: #5a6c7d;
    margin: 4px 0 10px 0;
}

.flow-bar {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0;
    margin: 8px 0 4px 0;
    flex-wrap: wrap;
}
.flow-step {
    background: #ffffff;
    border: 1px solid #cfd8e3;
    border-radius: 8px;
    padding: 10px 20px;
    text-align: center;
    min-width: 110px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}
.flow-step .fs-label {
    font-weight: 700;
    font-size: 0.82rem;
    color: #0d2137;
}
.flow-step .fs-sub {
    font-size: 0.7rem;
    color: #5a6c7d;
    margin-top: 2px;
}
.flow-arrow {
    font-size: 1.1rem;
    color: #0066cc;
    padding: 0 6px;
    font-weight: 700;
}
</style>""", unsafe_allow_html=True)
