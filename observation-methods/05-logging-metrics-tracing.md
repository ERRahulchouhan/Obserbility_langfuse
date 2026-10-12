# Method 5: Logging + metrics + tracing together

This is the production monitoring approach.

## What it does

It combines:

- traces for request flow
- logs for failure details
- metrics for latency, throughput, and error rate

## When to use it

Use this when:

- you need dashboards and alerting
- you want to track latency and request success
- you need production monitoring

## Example 1: log the request result

```python
import logging
import time

logging.basicConfig(level=logging.INFO)

start = time.time()
try:
    answer = rag_pipeline(question, chunks)
    latency = time.time() - start
    logging.info(
        "rag_request_success latency=%.3fs answer_len=%d",
        latency,
        len(answer),
    )
except Exception as exc:
    logging.exception("rag_request_failed error=%s", str(exc))
```

## Example 2: structured request metrics

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

How it works in RAG:

- trace shows the flow
- logs show raw errors/debugging details
- metrics show runtime trends and alerts

## Summary

This is a strong production pattern, but for learning and small demos, a simpler Langfuse trace is often enough.
