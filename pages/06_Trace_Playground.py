import os
from pathlib import Path

import streamlit as st
from dotenv import dotenv_values, load_dotenv
from langfuse import get_client
from openai import OpenAI

from rag import answer_question, chunk_text

project_dir = Path(__file__).resolve().parents[1]
env_file = project_dir / ".env"
load_dotenv(env_file)
for key, value in dotenv_values(env_file).items():
    if value and not os.getenv(key):
        os.environ[key] = value

st.set_page_config(page_title="Trace Test | Fieldnotes", layout="wide")
st.title("Trace test")
st.write("Run a sample RAG request and inspect the observations it creates.")

has_langfuse = bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))
has_openai = bool(os.getenv("OPENAI_API_KEY"))
status_col, backend_col = st.columns(2)
status_col.metric("Langfuse tracing", "Configured" if has_langfuse else "Not configured")
backend_col.metric("Answer generation", "OpenAI available" if has_openai else "Offline only")

with st.form("trace_test_form"):
    question = st.text_input(
        "Test question",
        value="What can teams inspect with Langfuse?",
    )
    include_generation = st.checkbox(
        "Call OpenAI for answer generation (uses API credits)",
        value=False,
        disabled=not has_openai,
    )
    run_test = st.form_submit_button("Run trace test", type="primary")

if run_test:
    sample_path = project_dir / "sample_data.md"
    sample_text = sample_path.read_text(encoding="utf-8")
    chunks = chunk_text(sample_text, source=sample_path.name)
    langfuse_client = get_client() if has_langfuse else None
    openai_client = OpenAI() if include_generation and has_openai else None

    with st.spinner("Running retrieval and recording observations…"):
        result = answer_question(
            question,
            chunks,
            openai_client=openai_client,
            langfuse_client=langfuse_client,
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        )
        if langfuse_client is not None:
            langfuse_client.flush()

    st.session_state["trace_test_result"] = {
        "answer": result.answer,
        "sources": result.sources,
        "question": question,
        "generation": openai_client is not None and bool(result.sources),
        "sent_to_langfuse": langfuse_client is not None,
    }

test_result = st.session_state.get("trace_test_result")
if test_result:
    st.divider()
    st.subheader("Test result")
    if test_result["sent_to_langfuse"]:
        st.success("Trace flushed to Langfuse. Open Tracing to inspect this request.")
        langfuse_url = os.getenv("LANGFUSE_BASE_URL", "http://localhost:3000").rstrip("/")
        st.link_button("Open Langfuse", langfuse_url)
    else:
        st.warning("Local test completed, but no trace was sent. Configure Langfuse keys in .env.")

    st.markdown(f"**Question:** {test_result['question']}")
    st.markdown(f"**Answer:** {test_result['answer']}")
    if has_openai and not test_result["generation"] and test_result["sources"]:
        st.caption("OpenAI was available but left unchecked; this test made no model API call.")
    st.markdown("**Retrieved passages**")
    if test_result["sources"]:
        for source in test_result["sources"]:
            st.markdown(f"- `{source.source}` · relevance `{source.score:.3f}`")
    else:
        st.info("No passage matched, so the trace contains retrieval but no generation.")

    st.subheader("Trace shape")
    trace_steps = ["rag-query", "└─ retrieve-context"]
    if test_result["generation"]:
        trace_steps.append("   └─ answer-generation (generation)")
    st.code("\n".join(trace_steps), language="text")
    st.caption(
        "The root observation covers the request. Retrieval is a child span; "
        "answer-generation appears when a matching passage and OpenAI generation are enabled."
    )