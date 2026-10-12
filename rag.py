# Langfuse observability cheat sheet for RAG:
# - @observe() = whole request trace
# - start_as_current_observation() = child step/span inside the request
# - observation.update() = add input/output/metadata to a span
# - update_current_trace() = add trace-level metadata (user, session, tags)
# - update_current_observation() = update the active observation
# - CallbackHandler() = automatic LangChain tracing
# - flush() = send all pending traces to Langfuse
# - get_client() = create the Langfuse client at app startup
#
# Typical RAG structure:
#   root trace: rag-query
#   child spans: retrieve-context, rerank, guardrail, answer-generation
#   final output: answer + retrieved docs + metadata
#
# Example:
#   @observe()
#   def answer_question(...):
#       with langfuse_client.start_as_current_observation(name="retrieve-context") as span:
#           docs = retrieve(...)
#           span.update(output=docs)
#
#   or:
#       with langfuse_client.start_as_current_observation(name="answer-generation",
#           as_type="generation") as gen:
#           response = model.generate(...)
#           gen.update(output=response)
#
# Separate examples:
#   1) whole request trace:
#      @observe()
#      def answer_question(...):
#          ...
#
#   2) separate child steps:
#      def answer_question(...):
#          with langfuse_client.start_as_current_observation(name="retrieve-context") as span:
#              docs = retrieve(...)
#              span.update(output=docs)
#
#          with langfuse_client.start_as_current_observation(name="answer-generation") as gen:
#              answer = call_llm(...)
#              gen.update(output=answer)
#
#   3) update current trace and current observation metadata:
#      langfuse_client.update_current_trace(user_id="u123", session_id="s1", tags=["rag"])
#      current_observation.update(metadata={"tenant": "acme"}, output={"answer": answer})

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass(frozen=True)
class DocumentChunk:
    source: str
    text: str


@dataclass(frozen=True)
class RetrievedChunk:
    source: str
    text: str
    score: float


@dataclass(frozen=True)
class RagResult:
    answer: str
    sources: list[RetrievedChunk]


def chunk_text(
    text: str, source: str, chunk_words: int = 140, overlap_words: int = 24
) -> list[DocumentChunk]:
    words = text.split()
    if not words:
        return []

    chunks = []
    step = max(1, chunk_words - overlap_words)
    for start in range(0, len(words), step):
        excerpt = " ".join(words[start : start + chunk_words])
        if excerpt:
            chunks.append(DocumentChunk(source=source, text=excerpt))
        if start + chunk_words >= len(words):
            break
    return chunks


def retrieve(question: str, chunks: list[DocumentChunk], top_k: int = 4) -> list[RetrievedChunk]:
    if not question.strip() or not chunks:
        return []

    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
    try:
        matrix = vectorizer.fit_transform([chunk.text for chunk in chunks] + [question])
    except ValueError:
        return []

    scores = cosine_similarity(matrix[-1], matrix[:-1]).ravel()
    ranked_indices = scores.argsort()[::-1]
    return [
        RetrievedChunk(chunks[index].source, chunks[index].text, float(scores[index]))
        for index in ranked_indices[:top_k]
        if scores[index] > 0
    ]


@contextmanager
def observation(
    langfuse_client: Any,
    *,
    name: str,
    as_type: str = "span",
    input: Any = None,
    **attributes: Any,
) -> Iterator[Any]:
    if langfuse_client is None:
        yield None
        return

    with langfuse_client.start_as_current_observation(
        name=name, as_type=as_type, input=input, **attributes
    ) as current_observation:
        yield current_observation


def answer_question(
    question: str,
    chunks: list[DocumentChunk],
    *,
    openai_client: Any = None,
    langfuse_client: Any = None,
    model: str = "gpt-4o-mini",
) -> RagResult:
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

        if not sources:
            answer = "I couldn't find a relevant passage in the indexed documents."
        elif openai_client is None:
            first_source = sources[0]
            answer = (
                "Generation is offline. The closest matching passage is from "
                f"{first_source.source}:\n\n> {first_source.text}"
            )
        else:
            context = "\n\n".join(
                f"[Source: {source.source}]\n{source.text}" for source in sources
            )
            prompt = (
                "Answer the question using only the provided context. If the context does "
                "not contain the answer, say so. Cite sources by their [Source: ...] name.\n\n"
                f"Context:\n{context}\n\nQuestion: {question}"
            )
            with observation(
                langfuse_client,
                name="answer-generation",
                as_type="generation",
                model=model,
                input={"question": question, "context": context},
            ) as generation:
                try:
                    response = openai_client.chat.completions.create(
                        model=model,
                        messages=[
                            {
                                "role": "system",
                                "content": "You are a careful, source-grounded assistant.",
                            },
                            {"role": "user", "content": prompt},
                        ],
                        temperature=0.2,
                    )
                    answer = response.choices[0].message.content or "No answer was generated."
                    if generation is not None:
                        generation.update(output=answer)
                except Exception as error:
                    if generation is not None:
                        generation.update(level="ERROR", status_message=str(error))
                    raise

        if trace is not None:
            trace.update(output={"answer": answer, "source_count": len(sources)})
        return RagResult(answer=answer, sources=sources)