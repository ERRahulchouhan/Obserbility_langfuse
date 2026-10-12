from pathlib import Path

import streamlit as st

st.set_page_config(page_title="Logs, Metrics, and Traces | Fieldnotes", layout="wide")
guide_path = Path(__file__).resolve().parents[1] / "observation-methods" / "05-logging-metrics-tracing.md"
st.markdown(guide_path.read_text(encoding="utf-8"))