import os
from io import BytesIO
from pathlib import Path

import streamlit as st
from dotenv import dotenv_values, load_dotenv
from langfuse import get_client
from openai import OpenAI
from pypdf import PdfReader

from rag import DocumentChunk, answer_question, chunk_text

project_dir = Path(__file__).resolve().parents[1]
env_file = project_dir / ".env"
load_dotenv(env_file)
for key, value in dotenv_values(env_file).items():
    if value and not os.getenv(key):
        os.environ[key] = value

st.set_page_config(page_title="Fieldnotes | RAG", page_icon="⌕", layout="wide")
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@400;500;600;700&family=Newsreader:opsz,wght@6..72,500;6..72,600&display=swap');
    :root { --ink: #202925; --muted: #66736c; --line: #dce3dc; --paper: #f5f7f3; --green: #216b50; --lime: #d9ed72; }
    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; color: var(--ink); }
    .stApp { background: var(--paper); }
    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stSidebar"] { background: #edf2ec; border-right: 1px solid var(--line); }
    h1, h2, h3 { font-family: 'Newsreader', Georgia, serif !important; letter-spacing: 0 !important; }
    h1 { font-size: 2.25rem !important; }
    .eyebrow { color: var(--green); font: 500 0.72rem 'DM Mono', monospace; text-transform: uppercase; }
    .status { display: inline-flex; gap: 8px; align-items: center; color: var(--muted); font: 400 0.75rem 'DM Mono', monospace; }
    .status::before { content: ''; width: 8px; height: 8px; background: var(--lime); border: 1px solid #93a83f; border-radius: 50%; }
    div[data-testid="stForm"] { border: 1px solid var(--line); background: white; padding: 1.15rem; border-radius: 6px; }
    div.stButton > button[kind="primary"], div[data-testid="stFormSubmitButton"] button { background: var(--green); border-color: var(--green); }
    div[data-testid="stExpander"] { border-color: var(--line); background: white; border-radius: 5px; }
    code, .mono { font-family: 'DM Mono', monospace; }
    </style>
    """,
    unsafe_allow_html=True,
)


def read_uploaded_file(uploaded_file) -> str:
    data = uploaded_file.getvalue()
    if uploaded_file.name.lower().endswith(".pdf"):
        reader = PdfReader(BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return data.decode("utf-8", errors="replace")


def make_chunks(documents: list[tuple[str, str]]) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    for source, text in documents:
        chunks.extend(chunk_text(text, source=source))
    return chunks


if "chunks" not in st.session_state:
    st.session_state.chunks = []
if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.markdown('<p class="eyebrow">FIELDNOTES / KNOWLEDGE</p>', unsafe_allow_html=True)
    st.subheader("Your sources")
    uploads = st.file_uploader(
        "Add documents",
        type=["txt", "md", "pdf"],
        accept_multiple_files=True,
        help="Text, Markdown, and text-based PDFs",
    )
    if st.button("Index uploaded files", use_container_width=True, disabled=not uploads):
        documents = [(file.name, read_uploaded_file(file)) for file in uploads]
        st.session_state.chunks = make_chunks(documents)
        st.session_state.messages = []
        st.rerun()

    if st.button("Load sample notes", use_container_width=True):
        sample_path = project_dir / "sample_data.md"
        with sample_path.open(encoding="utf-8") as sample_file:
            st.session_state.chunks = make_chunks([("sample_data.md", sample_file.read())])
        st.session_state.messages = []
        st.rerun()

    st.divider()
    st.caption(f"{len(st.session_state.chunks)} indexed passages")
    st.caption("OpenAI generation: on" if os.getenv("OPENAI_API_KEY") else "OpenAI generation: offline")
    has_langfuse = bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))
    st.caption("Langfuse tracing: on" if has_langfuse else "Langfuse tracing: not configured")

st.markdown('<p class="eyebrow">RETRIEVAL-AUGMENTED QA</p>', unsafe_allow_html=True)
st.title("Ask your sources")
st.markdown(
    '<span class="status">LOCAL RETRIEVAL</span> &nbsp; · &nbsp; '
    '<span class="status">TRACES TO LANGFUSE</span>',
    unsafe_allow_html=True,
)
st.write("")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("sources"):
            with st.expander(f"Retrieved passages · {len(message['sources'])}"):
                for source in message["sources"]:
                    st.markdown(f"**{source.source}** · relevance {source.score:.2f}")
                    st.write(source.text)

with st.form("question_form", clear_on_submit=True):
    question = st.text_input("Question", placeholder="What do the documents say about…")
    submitted = st.form_submit_button("Search and answer", type="primary")

if submitted and question.strip():
    if not st.session_state.chunks:
        st.warning("Add documents or load the sample notes to begin.")
    else:
        st.session_state.messages.append({"role": "user", "content": question})
        openai_client = OpenAI() if os.getenv("OPENAI_API_KEY") else None
        has_langfuse = bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))
        langfuse_client = get_client() if has_langfuse else None
        with st.spinner("Searching and composing an answer…"):
            result = answer_question(
                question,
                st.session_state.chunks,
                openai_client=openai_client,
                langfuse_client=langfuse_client,
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            )
        st.session_state.messages.append(
            {"role": "assistant", "content": result.answer, "sources": result.sources}
        )
        if langfuse_client is not None:
            langfuse_client.flush()
        st.rerun()