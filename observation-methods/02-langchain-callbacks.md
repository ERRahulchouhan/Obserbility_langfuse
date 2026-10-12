# Method 2: LangChain CallbackHandler

This method is for apps built with LangChain.

## What it does

`CallbackHandler()` listens to LangChain events and automatically sends them to Langfuse.

## When to use it

Use this when:

- your code uses LangChain `Runnable`, `Chain`, `Agent`, or `LLM`
- you want automatic tracing without manual wrapped spans
- you want to see retriever, prompt, tool, and model calls automatically

## When not to use it

Avoid this when:

- your app is plain Python with direct OpenAI SDK calls
- you want explicit naming and control over each step

## Example 1: direct chain tracing

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

How it works:

- `handler` subscribes to events from the chain
- Langfuse records prompt and model execution automatically
- you do not need to manually wrap every step

## Example 2: RAG retriever + answer chain

```python
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

How it works in RAG:

- retriever step is traced automatically
- prompt assembly is traced automatically
- model call is traced automatically
- final answer can be inspected in Langfuse

## Summary

This method is best for LangChain applications where you want less boilerplate and more automatic visibility.

It is great for:

- chains
- retrievers
- tools
- agents

It is not ideal when you need very custom step naming or custom Python instrumentation.
