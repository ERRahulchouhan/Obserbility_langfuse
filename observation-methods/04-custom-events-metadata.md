# Method 4: Custom events and metadata

This method adds business and application context to your trace.

## What it does

You attach data like user ID, tenant, model version, prompt version, session ID, and tags to the observation.

## When to use it

Use this when:

- you need user or tenant tracking
- you want to compare prompt versions
- you want to evaluate retrieval quality
- you want custom metadata beyond basic request tracing

## Example 1: observation metadata

```python
from langfuse import get_client

langfuse_client = get_client()

with langfuse_client.start_as_current_observation(
    name="user-feedback",
    metadata={"tenant": "acme", "user_id": "u123", "model_version": "v2"},
) as span:
    span.update(output={"rating": 5, "comment": "helpful"})
```

## Example 2: RAG evaluation metadata

```python
from langfuse import get_client

langfuse_client = get_client()

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

How it works in RAG:

- metadata makes the trace useful for debug and analysis
- you can inspect which users, tenants, or prompt versions caused issues
- you can compare retrieval quality across sessions and models

## Summary

This is perfect for production apps where analysis and debugging require more context than raw traces alone.
