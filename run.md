# Langfuse observability guide

This project already shows one strong pattern: a RAG app can trace a user request from input to retrieval and model generation using Langfuse.

## 1) What is observability?

Observability means you can answer questions like:

- What happened in the app?
- Which step failed or slowed down?
- What input did the model receive?
- What answer or error did the model return?
- Which document chunk or tool call was used?

For LLM apps, observability usually covers:

- traces
- spans
- generations
- logs
- metrics
- errors

In this repo, the most useful flow is:

- `rag-query` = whole request trace
- `retrieve-context` = retrieval logic
- `answer-generation` = LLM call

That gives a simple but complete view of how a question is processed.

## 2) How many ways can we do observability with Langfuse?

There are several common ways.

### Quick Langfuse method cheat sheet for RAG

- `get_client()`
  - What it does: creates the Langfuse client object.
  - Where it is used: at application startup, before any trace is created.
  - In RAG: used once when the app starts or when a request pipeline is initialized, so that all later traces can use the same client.

- `@observe()`
  - What it does: automatically traces a function as an observation.
  - Where it is used: on a function like `answer_question()`, `generate_response()`, or a full RAG pipeline method.
  - In RAG: best for tracing the entire request flow in one place.

- `start_as_current_observation()`
  - What it does: manually creates a child observation/span under the current trace.
  - Where it is used: inside a function to split the work into smaller steps.
  - In RAG: use for retrieval, reranking, prompt assembly, guardrails, and LLM generation.

- `observation.update()`
  - What it does: adds input, output, metadata, or status to an existing observation.
  - Where it is used: after retrieval or model completion.
  - In RAG: perfect for attaching retrieved docs, similarity scores, prompt content, output answer, or errors.

- `update_current_trace()`
  - What it does: updates the active trace context for the current request.
  - Where it is used: when you want to add session, user, tags, environment, or request metadata to the overall trace.
  - In RAG: use it for `session_id`, `user_id`, `tenant`, `tags`, or request metadata.

- `update_current_observation()`
  - What it does: updates the current observation object without creating a new one.
  - Where it is used: during or after a step like retrieval or generation.
  - In RAG: useful for adding model name, prompt, answer, score, or custom attributes.

- `CallbackHandler()`
  - What it does: automatically captures LangChain events from chains, tools, retrievers, and LLM calls.
  - Where it is used: in LangChain workflows.
  - In RAG: use to trace chain execution, retriever steps, tool calls, and model calls without manual wrapping everywhere.

- `flush()`
  - What it does: sends all pending Langfuse events to the backend.
  - Where it is used: at the end of a request or before app shutdown.
  - In RAG: call after response processing or right before the app exits so traces are not lost.

This is the practical mental model for a RAG pipeline:

- `get_client()` sets up the connection
- `@observe()` creates the full request trace (root observation)
- `start_as_current_observation()` creates child spans for retrieval, rerank, guardrail, and generation steps
- `update()` adds the actual data like input/output/metadata
- `CallbackHandler()` handles automatic tracing in LangChain
- `flush()` pushes everything to Langfuse

In simple words:

- `@observe()` = whole request trace
- `start_as_current_observation()` = child step inside that trace

## Method pages

- [Method 1: Manual Langfuse SDK](observation-methods/01-manual-sdk.md)
- [Method 2: LangChain CallbackHandler](observation-methods/02-langchain-callbacks.md)
- [Method 3: OpenTelemetry tracing](observation-methods/03-opentelemetry.md)
- [Method 4: Custom events and metadata](observation-methods/04-custom-events-metadata.md)
- [Method 5: Logging + metrics + tracing](observation-methods/05-logging-metrics-tracing.md)

---

### Method 1: Manual instrumentation with the Langfuse SDK
Use this when:

- you have Python code and custom app logic
- you want full control of each trace/span
- you are building a RAG pipeline, workflow, or agent

Best for:

- custom LLM apps
- tool-calling systems
- retrieval systems
- backend logic not built on LangChain

When not to use it:

- when you want a framework-native solution and your app is already using LangChain heavily
- when a full distributed tracing stack is already in place and you want standard OTel-based signals

Example 1: simple root trace

```python
from langfuse import get_client

langfuse_client = get_client()

with langfuse_client.start_as_current_observation(
    name="rag-query",
    input={"question": "What is observability?"},
) as trace:
    print("request started")
    trace.update(output={"status": "received"})
```

Example 2: retrieval step + answer step

```python
from langfuse import get_client

langfuse_client = get_client()


def rag_pipeline(question: str, chunks: list):
    with langfuse_client.start_as_current_observation(
        name="rag-query",
        input={"question": question},
    ) as trace:
        with langfuse_client.start_as_current_observation(
            name="retrieve-context",
            input={"question": question},
        ) as retrieval_span:
            docs = retrieve(question, chunks)
            retrieval_span.update(
                output=[{"source": d.source, "score": d.score, "text": d.text} for d in docs]
            )

        with langfuse_client.start_as_current_observation(
            name="answer-generation",
            as_type="generation",
            model="gpt-4o-mini",
            input={"question": question, "context": docs},
        ) as generation:
            answer = "AI answer based on retrieved docs"
            generation.update(output=answer)

        trace.update(output={"answer": answer, "docs_count": len(docs)})
        return answer
```

Example 3: update the current trace with metadata

```python
from langfuse import get_client

langfuse_client = get_client()

with langfuse_client.start_as_current_observation(
    name="rag-query",
    input={"question": "What is Langfuse?"},
) as trace:
    langfuse_client.update_current_trace(
        user_id="u123",
        session_id="s-001",
        tags=["rag", "demo"],
    )
    trace.update(output={"status": "ok"})
```

This is the method already used in this project.

---

### Method 2: LangChain callbacks
Use this when:

- your app uses LangChain `Runnable`, `Chain`, `Agent`, or `LLM` objects
- you want automatic trace collection without manually wrapping logic

Best for:

- LangChain apps
- agent workflows
- chains with multiple steps
- tool execution tracking

When not to use it:

- when your app is custom Python logic without LangChain
- when your code already uses direct OpenAI or simple SDK calls

Example 1: direct chain tracing

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langfuse.langchain import CallbackHandler

handler = CallbackHandler()
# handler is the Langfuse callback object that listens to LangChain events
# and sends chain/tool/retriever/LLM activity to Langfuse automatically

prompt = ChatPromptTemplate.from_messages([
    ("system", "Answer using the retrieved context."),
    ("human", "{question}"),
])

llm = ChatOpenAI(model="gpt-4o-mini")
chain = prompt | llm

response = chain.invoke(
    {"question": "What is observability?"},
    config={"callbacks": [handler]},
)
print(response.content)
```

Example 2: RAG retriever + answer chain

```python
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langfuse.langchain import CallbackHandler

handler = CallbackHandler()
retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

answer_chain = (
    {"context": retriever, "question": "{question}"}
    | prompt
    | llm
)

result = answer_chain.invoke(
    {"question": "How does Langfuse track LLM calls?"},
    config={"callbacks": [handler]},
)
```

This automatically records chain/tool/LLM events in Langfuse.

---

### Method 3: OpenTelemetry (OTel) integration
Use this when:

- you already have an observability platform or microservices architecture
- you want standard tracing for multiple services
- you need logs, traces, and metrics in a consistent vendor-neutral format

Best for:

- enterprise systems
- multi-service apps
- APIs and backend platforms
- teams using OpenTelemetry in production

When not to use it:

- for very small apps where direct Langfuse SDK instrumentation is simpler
- when you are building a quick prototype and do not want extra setup overhead

Example 1: basic OTel span

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import Resource

resource = Resource.create({"service.name": "rag-service"})
provider = TracerProvider(resource=resource)
tracer = provider.get_tracer(__name__)

with tracer.start_as_current_span("rag-request") as span:
    span.set_attribute("user.id", "abc123")
    span.set_attribute("question", "How does retrieval work?")
    print("OTel trace started")
```

Example 2: trace retrieval and model call together

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span("retrieval") as retrieval_span:
    docs = retrieve(question, chunks)
    retrieval_span.set_attribute("retrieved_docs", len(docs))

with tracer.start_as_current_span("generation") as generation_span:
    answer = "Generated answer"
    generation_span.set_attribute("model", "gpt-4o-mini")
```

Typical pattern:

- instrument your app with OTel
- export telemetry to Langfuse or another backend
- correlate app, database, LLM, and infra traces

---

### Method 4: SDK + custom events and metadata
Use this when:

- you want business-specific details in Langfuse
- you need custom attributes like user ID, tenant ID, prompt version, environment
- you want to track features beyond LLM calls

Best for:

- user analytics
- application events
- feature-level monitoring
- custom prompt versioning and metadata

When not to use it:

- when you only need a simple LLM request trace
- when more standard spans/generation tracing is enough

Example 1: custom observation metadata

```python
langfuse_client = get_client()

with langfuse_client.start_as_current_observation(
    name="user-feedback",
    metadata={"tenant": "acme", "user_id": "u123", "model_version": "v2"},
) as span:
    span.update(output={"rating": 5, "comment": "helpful"})
```

Example 2: RAG retrieval-eval metadata

```python
with langfuse_client.start_as_current_observation(
    name="retrieval-eval",
    input={"query": question},
) as eval_span:
    eval_span.update(
        output={
            "retrieved_docs": [doc.text for doc in docs],
            "scores": [doc.score for doc in docs],
            "user_id": "u123",
            "tenant": "acme",
        }
    )
```

---

### Method 5: Logging + metrics + tracing together
Use this when:

- you need production-grade monitoring
- you want both technical and business metrics
- you need to alert on failures, latency, or token usage

Best for:

- production deployments
- alerting and SRE workflows
- dashboards and incident response

When not to use it:

- for a learning project or simple RAG demo
- when you do not need alerting or infra monitoring yet

Example 1: log the request result

```python
import logging
import time

logging.basicConfig(level=logging.INFO)

start = time.time()
try:
    answer = rag_pipeline(question, chunks)
    latency = time.time() - start
    logging.info("rag_request_success latency=%.3fs answer_len=%d", latency, len(answer))
except Exception as exc:
    logging.exception("rag_request_failed error=%s", str(exc))
```

Example 2: structured metrics + trace correlation

```python
import time

start = time.time()
answer = rag_pipeline(question, chunks)
latency_ms = (time.time() - start) * 1000

print({
    "event": "rag_latency",
    "latency_ms": round(latency_ms, 2),
    "question_length": len(question),
    "answer_length": len(answer),
})
```

A healthy stack often includes:

- traces for request flow
- logs for error details
- metrics for latency, throughput, error rate
- dashboards for trends and drill-downs

---

## 3) Which method is best for this project?

For this project, the best approach is Method 1 with a few custom metadata attributes.

Why?

- the app is a simple Python RAG workflow
- you need to track retrieval and generation clearly
- the code is already organized around a request flow
- Langfuse traces are easy to inspect and debug

This project already implements a good model:

- root observation: `rag-query`
- retrieval observation: `retrieve-context`
- generation observation: `answer-generation`

That is usually enough for a first production-grade LLM observability setup.

## 4) How this repo does it

The app sets up Langfuse in [app.py](app.py):

```python
from langfuse import get_client

langfuse_client = get_client() if has_langfuse else None
```

Then it passes the client into the answer workflow:

```python
result = answer_question(
    question,
    st.session_state.chunks,
    openai_client=openai_client,
    langfuse_client=langfuse_client,
    model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
)
```

The actual trace logic is in [rag.py](rag.py):

```python
with observation(
    langfuse_client,
    name="rag-query",
    input={"question": question},
) as trace:
    with observation(
        langfuse_client,
        name="retrieve-context",
        input={"question": question, "chunk_count": len(chunks)},
    ) as retrieval_span:
        sources = retrieve(question, chunks)
        if retrieval_span is not None:
            retrieval_span.update(
                output=[
                    {"source": item.source, "text": item.text, "score": item.score}
                    for item in sources
                ]
            )
```

And model output is traced here:

```python
with observation(
    langfuse_client,
    name="answer-generation",
    as_type="generation",
    model=model,
    input={"question": question, "context": context},
) as generation:
    response = openai_client.chat.completions.create(...)
    answer = response.choices[0].message.content or "No answer was generated."
```

## 5) How to use Langfuse in this app

From the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

Then open:

- app: http://127.0.0.1:8501
- Langfuse UI: http://localhost:3000

In Langfuse, open the Tracing section and look for `rag-query` traces.

You should be able to see:

- input question
- retrieved chunks
- selected source documents
- model answer
- error states if something fails

## 6) When to use versus when not to use

### Use manual Langfuse tracing when:

- you want control over each step
- you want simple and fast setup
- your app is custom and not heavily framework-based
- you are building a local demo or prototype

### Do not use manual tracing when:

- your app is already built on LangChain and you want automatic handling
- you need broad platform-wide distributed tracing from many services
- you are already using OTel and want standard instrumentation patterns

### Use LangChain callbacks when:

- you are in a LangChain workflow
- you want less manual boilerplate
- you need agent/tool call visibility automatically

### Do not use LangChain callbacks when:

- your code uses plain OpenAI SDK calls and custom business logic
- you want explicit control over each span name and metadata

### Use OTel when:

- you need enterprise-level standardization
- multiple services and systems must be correlated
- logs, traces, and metrics must be unified across stacks

### Do not use OTel when:

- you are building a small local app and want the fastest path to working tracing

### Use custom event metadata when:

- you need business, user, or tenant context
- you want to track experiments, prompt versions, and environment details

### Do not use custom metadata if:

- it adds noise and does not improve debugging or evaluation

## 7) Best practice for production

For a real application, this is the usual pattern:

- trace the full user request
- trace retrieval separately
- trace model generation separately
- log model errors and latency
- attach metadata such as:
  - user ID
  - tenant ID
  - prompt version
  - model name
  - environment
  - request ID

A good production trace should answer:

- who asked?
- what did the system retrieve?
- what prompt did the model see?
- what answer was returned?
- what failed or took too long?

## 8) Summary

The main observability methods are:

1. manual Langfuse tracing
2. LangChain callbacks
3. OpenTelemetry integration
4. custom events + metadata
5. logs + metrics + traces together

For this project, the most practical approach is:

- manual Langfuse tracing with custom spans for retrieval and generation
- optionally add metadata like model, user, tenant, and environment

This is already the pattern used in [rag.py](rag.py), and it gives you high-value observability without unnecessary complexity.

If you want, I can next add a final section in [run.md](run.md) with a short comparison table of all methods and a recommended setup for production vs demo use.
