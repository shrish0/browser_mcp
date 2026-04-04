from typing import Callable, Dict

prompts: Dict[str, Dict[str, Callable[[str, str], str]]] = {
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
}
