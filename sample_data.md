# Langfuse observability notes

Langfuse is an open-source platform for LLM engineering. Teams use it to inspect traces, generations, prompts, and evaluation results for applications that use language models.

A trace represents one end-to-end request. Observations are the individual operations inside that trace. A span is useful for application work such as retrieval, while a generation represents an LLM call and can include a model name, input, output, and token usage.

In the Python SDK, `get_client()` creates or returns the Langfuse client. `start_as_current_observation()` can be used as a context manager to create nested observations. The outer request span can contain a retrieval span and a generation observation. Context managers automatically close observations when their blocks exit.

Set `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` to send traces to Langfuse Cloud. Set `LANGFUSE_BASE_URL` when using a different region or a self-hosted instance. The SDK buffers observations, so short-lived scripts should call `flush()` before exiting.

Useful RAG traces show the user question, which passages were retrieved, the generation model, the prompt context, and the final answer. Avoid putting secrets or sensitive personal data in trace inputs and outputs.