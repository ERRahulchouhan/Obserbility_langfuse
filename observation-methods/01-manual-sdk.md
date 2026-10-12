# Method 1: Manual Langfuse instrumentation

This is the most direct and practical method for a custom RAG app.

## What it does

It creates observations manually inside your code using `start_as_current_observation()`.

## When to use it

Use this when:

- your app is custom Python code
- you want complete control of each trace step
- you are building a RAG pipeline or custom workflow
- you want to clearly split retrieval, reranking, guardrails, and generation

## When not to use it

Avoid this if:

- your app is already built on LangChain and you want automatic tracing
- you already use OpenTelemetry across many services

## Example 1: single observation

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

How it works:

- `start_as_current_observation()` creates one observation
- `trace.update(...)` adds the output data
- Langfuse stores it as a trace/span in the UI

## Example 2: full RAG flow

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
                output=[
                    {"source": d.source, "score": d.score, "text": d.text}
                    for d in docs
                ]
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

How it works in RAG:

- `rag-query` = root trace for the whole user request
- `retrieve-context` = child span for retrieval
- `answer-generation` = child generation for LLM output

This is the same pattern used by this project in [rag.py](../rag.py).

## Example 3: add metadata to the trace

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

## Summary

This is the best method for this project because it gives you precise control over:

- full request tracking
- retrieval child span
- generation child span
- metadata like user/session/tags

Use this when you want a clear RAG trace tree.
