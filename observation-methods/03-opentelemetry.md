# Method 3: OpenTelemetry tracing

This is the standard distributed tracing approach used across services.

## What it does

OpenTelemetry creates spans that represent service operations and can be exported to Langfuse or another backend.

## When to use it

Use this when:

- you already use OTel in production
- your app is part of a larger microservices architecture
- you want standard tracing across systems

## When not to use it

Avoid this when:

- you are doing a small local RAG demo
- you want the quickest setup with minimal overhead

## Example 1: basic span

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

## Example 2: trace retrieval and generation separately

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

How it works in RAG:

- retrieval is one span
- generation is another span
- both can be correlated under the same request trace

## Summary

This is very powerful for enterprise systems, but for a simple local RAG app, direct Langfuse SDK instrumentation is usually simpler.
