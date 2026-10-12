from pathlib import Path

import streamlit as st

st.set_page_config(page_title="Manual Langfuse SDK | Fieldnotes", layout="wide")
guide_path = Path(__file__).resolve().parents[1] / "observation-methods" / "01-manual-sdk.md"
st.markdown(guide_path.read_text(encoding="utf-8"))