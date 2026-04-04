from typing import Callable, Dict, List, Union

PromptFunction = Callable[[Union[str, List[str]], str], str]

prompts: Dict[str, Dict[str, PromptFunction]] = {
    "default": {
        "system": lambda question, context: (
            "You MUST answer ONLY from the provided context. "
            "If the answer is not present, say 'Not found in context'. "
            "Do NOT hallucinate or add external knowledge."
        ),
        "user": lambda question, context: f"{question}\n\nContext:\n{context}",
    },
    "qwen": {
        "system": lambda question, context: (
            "You MUST answer ONLY from the provided context. "
            "If the answer is not present, say 'Not found in context'. "
            "Do NOT hallucinate or add external knowledge."
        ),
        "user": lambda question, context: (
            "Please answer the following question based on the context provided.\n\n"
            f"Question: {question}\n\nContext:\n{context}"
        ),
    },
    "batch_default": {
        "system": lambda questions, context: (
            "You MUST answer ONLY from the provided context. "
            "If an answer is not found, return 'Not found in context'. "
            "Return answers in STRICT JSON format. Do NOT hallucinate or add external knowledge."
        ),
        "user": lambda questions, context: (
            "Answer the following questions based ONLY on the given context.\n\n"
            "Questions:\n"
            + "\n".join(
                f"{index + 1}. {question}" for index, question in enumerate(questions)
            )
            + f"\n\nContext:\n{context}\n\n"
            "Return response in this EXACT JSON format:\n"
            "{\n"
            '  "answers": [\n'
            '    {"question": "<question_1>", "answer": "..."},\n'
            '    {"question": "<question_2>", "answer": "..."}\n'
            "  ]\n"
            "}"
        ),
    },
    "batch_qwen": {
        "system": lambda questions, context: (
            "You MUST answer ONLY from the provided context. "
            "If an answer is not found, return 'Not found in context'. "
            "Return answers in STRICT JSON format. Do NOT hallucinate or add external knowledge."
        ),
        "user": lambda questions, context: (
            "Answer the following questions based ONLY on the given context.\n\n"
            "Questions:\n"
            + "\n".join(
                f"{index + 1}. {question}" for index, question in enumerate(questions)
            )
            + f"\n\nContext:\n{context}\n\n"
            "Return response in this EXACT JSON format:\n"
            "{\n"
            '  "answers": [\n'
            '    {"question": "<question_1>", "answer": "..."},\n'
            '    {"question": "<question_2>", "answer": "..."}\n'
            "  ]\n"
            "}"
        ),
    },
}
