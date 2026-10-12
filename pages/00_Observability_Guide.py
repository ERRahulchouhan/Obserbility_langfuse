from pathlib import Path
import os

import streamlit as st
from dotenv import dotenv_values, load_dotenv

from method_test_runner import run_method_test

st.set_page_config(page_title="Observability Guide | Fieldnotes", layout="wide")
project_dir = Path(__file__).resolve().parents[1]
env_file = project_dir / ".env"
load_dotenv(env_file)
for key, value in dotenv_values(env_file).items():
	if value and not os.getenv(key):
		os.environ[key] = value

guide_path = project_dir / "run.md"
st.markdown(guide_path.read_text(encoding="utf-8"))

st.divider()
st.header("Test the methods")
st.write("Run a real sample operation for each method. Tests use local sample notes and do not call OpenAI.")

method_labels = {
	"manual": "Manual Langfuse SDK",
	"langchain": "LangChain CallbackHandler",
	"otel": "OpenTelemetry",
	"metadata": "Custom events and metadata",
	"logs": "Logs, metrics, and tracing",
}
selected_method = st.selectbox("Method to test", list(method_labels.values()))
method_key = next(key for key, label in method_labels.items() if label == selected_method)
question = st.text_input("Test input", value="What can teams inspect with Langfuse?")
has_langfuse = bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))
st.caption("Langfuse delivery: configured" if has_langfuse else "Langfuse delivery: keys missing from .env")

if st.button("Run selected method", type="primary", disabled=not question.strip()):
	try:
		with st.spinner("Running the method test…"):
			st.session_state["method_test_result"] = run_method_test(
				method_key,
				question.strip(),
				project_dir / "sample_data.md",
			)
		st.session_state.pop("method_test_error", None)
	except Exception as error:
		st.session_state.pop("method_test_result", None)
		st.session_state["method_test_error"] = str(error)

if st.session_state.get("method_test_error"):
	test_error = st.session_state["method_test_error"]
	if "uuid_utils" in test_error or "langchain" in test_error.lower():
		st.error("The LangChain test dependencies are incomplete in this virtual environment.")
		st.code(
			r"""# Stop Streamlit first, then run from the project folder
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8502""",
			language="powershell",
		)
	else:
		st.error(f"Test failed: {test_error}")

test_result = st.session_state.get("method_test_result")
if test_result:
	st.subheader("Test result")
	if test_result["sent_to_langfuse"]:
		st.success("Langfuse export was flushed. Open Tracing to inspect the test.")
		langfuse_url = os.getenv("LANGFUSE_BASE_URL", "http://localhost:3000").rstrip("/")
		st.link_button("Open Langfuse", langfuse_url)
	else:
		st.warning("The method ran locally, but no Langfuse credentials are configured.")
	st.code(test_result["trace_shape"], language="text")
	st.json(test_result["details"])