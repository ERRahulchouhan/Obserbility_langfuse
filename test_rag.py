from rag import DocumentChunk, answer_question, chunk_text, retrieve


def test_chunk_text_keeps_source_and_overlap():
    chunks = chunk_text("one two three four five six", "notes.txt", chunk_words=4, overlap_words=2)

    assert len(chunks) == 2
    assert chunks[0].source == "notes.txt"
    assert chunks[0].text == "one two three four"
    assert chunks[1].text == "three four five six"


def test_retrieve_ranks_relevant_passage():
    chunks = [
        DocumentChunk("observability.md", "Langfuse records traces and generations for LLM applications."),
        DocumentChunk("cooking.md", "A sourdough starter needs flour, water, and regular feeding."),
    ]

    results = retrieve("How does Langfuse record LLM traces?", chunks)

    assert results
    assert results[0].source == "observability.md"
    assert results[0].score > 0


def test_answer_question_works_without_external_services():
    chunks = [DocumentChunk("notes.md", "Retrieval finds useful passages before answering a question.")]

    result = answer_question("How does retrieval help?", chunks)

    assert "Generation is offline" in result.answer
    assert result.sources[0].source == "notes.md"