import streamlit as st
st.set_page_config(page_title="Fieldnotes | Observability", page_icon="⌕", layout="wide")

pages = [
    st.Page("pages/00_RAG_App.py", title="Ask your sources", default=True),
    st.Page("pages/00_Observability_Guide.py", title="Observability overview"),
    st.Page("pages/01_Manual_Langfuse_SDK.py", title="Manual Langfuse SDK"),
    st.Page("pages/02_LangChain_Callbacks.py", title="LangChain callbacks"),
    st.Page("pages/03_OpenTelemetry.py", title="OpenTelemetry"),
    st.Page("pages/04_Custom_Events_Metadata.py", title="Custom events and metadata"),
    st.Page("pages/05_Logs_Metrics_Traces.py", title="Logs, metrics, and traces"),
    st.Page("pages/06_Trace_Playground.py", title="Trace test"),
]

st.navigation(pages).run()