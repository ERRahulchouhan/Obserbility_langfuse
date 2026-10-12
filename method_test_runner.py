import base64
import logging
import os
import time
from io import StringIO
from pathlib import Path
from typing import Any

from langfuse import get_client

from rag import answer_question, chunk_text, retrieve


def _langfuse_client() -> Any | None:
    if os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"):
        return get_client()
    return None


def _flush(client: Any | None) -> bool:
    if client is None:
        return False
    client.flush()
    return True


def _run_manual(question: str, chunks: list[Any], client: Any | None) -> dict[str, Any]:
    result = answer_question(question, chunks, langfuse_client=client)
    return {
        "sent_to_langfuse": _flush(client),
        "trace_shape": "rag-query\n└─ retrieve-context",
        "details": {
            "answer": result.answer,
            "retrieved_passages": len(result.sources),
            "sources": [source.source for source in result.sources],
        },
    }


def _run_langchain(question: str, client: Any | None) -> dict[str, Any]:
    from langchain_core.runnables import RunnableLambda
    from langfuse.langchain import CallbackHandler

    handler = CallbackHandler() if client is not None else None
    runnable = RunnableLambda(
        lambda values: {
            "result": f"Callback chain received: {values['question']}"
        }
    )
    config = {"callbacks": [handler]} if handler is not None else {}
    result = runnable.invoke({"question": question}, config=config)
    return {
        "sent_to_langfuse": _flush(client),
        "trace_shape": "RunnableLambda\n└─ Langfuse CallbackHandler",
        "details": {
            "chain_output": result["result"],
            "callback_attached": handler is not None,
        },
    }


def _run_otel(question: str, client: Any | None) -> dict[str, Any]:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    provider = TracerProvider(
        resource=Resource.create({"service.name": "fieldnotes-method-test"})
    )
    memory_exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(memory_exporter))
    if client is not None:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        credentials = (
            f"{os.environ['LANGFUSE_PUBLIC_KEY']}:{os.environ['LANGFUSE_SECRET_KEY']}"
        ).encode("utf-8")
        authorization = base64.b64encode(credentials).decode("ascii")
        base_url = os.getenv("LANGFUSE_BASE_URL", "http://localhost:3000").rstrip("/")
        exporter = OTLPSpanExporter(
            endpoint=f"{base_url}/api/public/otel/v1/traces",
            headers={"Authorization": f"Basic {authorization}"},
        )
        provider.add_span_processor(SimpleSpanProcessor(exporter))

    tracer = provider.get_tracer("fieldnotes.observability.test")
    try:
        with tracer.start_as_current_span("otel-test-request") as root_span:
            root_span.set_attribute("question", question)
            with tracer.start_as_current_span("otel-test-work") as child_span:
                child_span.set_attribute("operation", "sample instrumentation")
        provider.force_flush(timeout_millis=10000)
        span_count = len(memory_exporter.get_finished_spans())
    finally:
        provider.shutdown()

    return {
        "sent_to_langfuse": client is not None,
        "trace_shape": "otel-test-request\n└─ otel-test-work",
        "details": {
            "completed_spans": span_count,
            "service": "fieldnotes-method-test",
            "question_attribute": question,
        },
    }


def _run_metadata(question: str, client: Any | None) -> dict[str, Any]:
    metadata = {"demo": True, "method": "custom-metadata", "tenant": "sample"}
    if client is not None:
        with client.start_as_current_observation(
            name="metadata-test",
            input={"question": question},
            metadata=metadata,
        ) as observation:
            observation.update(output={"status": "metadata attached"})

    return {
        "sent_to_langfuse": _flush(client),
        "trace_shape": "metadata-test\n└─ input + metadata + output",
        "details": {"question": question, "metadata": metadata},
    }


def _run_logs(question: str, chunks: list[Any], client: Any | None) -> dict[str, Any]:
    captured_log = StringIO()
    handler = logging.StreamHandler(captured_log)
    logger = logging.getLogger("fieldnotes.observability.test")
    previous_level = logger.level
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    started = time.perf_counter()
    try:
        sources = retrieve(question, chunks)
        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        logger.info(
            "retrieval_complete source_count=%d latency_ms=%.3f",
            len(sources),
            latency_ms,
        )
        if client is not None:
            with client.start_as_current_observation(
                name="logs-metrics-traces-test",
                input={"question": question},
            ) as observation:
                with client.start_as_current_observation(
                    name="retrieve-context",
                    input={"question": question},
                ) as retrieval_span:
                    retrieval_span.update(
                        output={"source_count": len(sources), "latency_ms": latency_ms}
                    )
                observation.update(
                    output={"source_count": len(sources), "latency_ms": latency_ms}
                )
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)
        handler.close()

    return {
        "sent_to_langfuse": _flush(client),
        "trace_shape": "logs-metrics-traces-test\n└─ retrieve-context",
        "details": {
            "log": captured_log.getvalue().strip(),
            "metrics": {"retrieved_passages": len(sources), "latency_ms": latency_ms},
        },
    }


def run_method_test(method: str, question: str, sample_path: Path) -> dict[str, Any]:
    sample_text = sample_path.read_text(encoding="utf-8")
    chunks = chunk_text(sample_text, source=sample_path.name)
    client = _langfuse_client()

    if method == "manual":
        return _run_manual(question, chunks, client)
    if method == "langchain":
        return _run_langchain(question, client)
    if method == "otel":
        return _run_otel(question, client)
    if method == "metadata":
        return _run_metadata(question, client)
    if method == "logs":
        return _run_logs(question, chunks, client)
    raise ValueError(f"Unknown observability test method: {method}")