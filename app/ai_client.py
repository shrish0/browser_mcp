import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from openai import OpenAI

from prompts import prompts
from setting import get_settings

logger = logging.getLogger(__name__)

MODEL_CONFIG: Dict[str, str] = {
    "qwen/qwen3.6-plus:free": "qwen",
}

# Keyed singleton instances
_clients: Dict[str, "AIClient"] = {}


class _ModelState:
    def __init__(self) -> None:
        self.failure_count = 0
        self.disabled_until = 0.0

    def is_disabled(self) -> bool:
        return time.monotonic() < self.disabled_until

    def record_success(self) -> None:
        self.failure_count = 0
        self.disabled_until = 0.0

    def record_failure(self, threshold: int, reset_seconds: int) -> None:
        self.failure_count += 1
        if self.failure_count >= threshold:
            self.disabled_until = time.monotonic() + reset_seconds


def _safe_text(text: Optional[str]) -> str:
    if not text:
        return "Not found in context"
    return text.strip()


def _parse_response(response: Any) -> str:
    if response is None:
        return "Not found in context"

    if isinstance(response, dict):
        choices = response.get("choices")
    else:
        choices = getattr(response, "choices", None)

    if not choices:
        return "Not found in context"

    first_choice = choices[0] if isinstance(choices, list) else None
    if first_choice is None:
        return "Not found in context"

    if isinstance(first_choice, dict):
        message = first_choice.get("message")
        if isinstance(message, dict):
            return _safe_text(message.get("content"))
        return _safe_text(first_choice.get("text"))

    message = getattr(first_choice, "message", None)
    if message is not None:
        return _safe_text(getattr(message, "content", None))

    return _safe_text(getattr(first_choice, "text", None))


def build_payload(
    model: str,
    question: Union[str, List[str]],
    context: str,
    max_tokens: int,
) -> Dict[str, Any]:
    prompt_key = MODEL_CONFIG.get(model, "default")
    batch_key = f"batch_{prompt_key}"

    if isinstance(question, list):
        prompt = prompts.get(batch_key, prompts["batch_default"])
    else:
        prompt = prompts.get(prompt_key, prompts["default"])

    system_prompt = prompt["system"](question, context)
    user_prompt = prompt["user"](question, context)

    return {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": max_tokens,
    }


def batch_questions(questions: List[str], batch_size: int = 10) -> List[List[str]]:
    if batch_size < 1:
        batch_size = 1
    batch_size = min(batch_size, 20)
    return [questions[i : i + batch_size] for i in range(0, len(questions), batch_size)]


def _parse_batch_response(response: Any, questions: List[str]) -> List[Dict[str, str]]:
    raw_text = _parse_response(response)
    try:
        parsed = json.loads(raw_text)
    except Exception:
        logger.warning("Batch response is not valid JSON")
        return [{"question": q, "answer": "Not found in context"} for q in questions]

    if not isinstance(parsed, dict):
        logger.warning("Batch response JSON is not an object")
        return [{"question": q, "answer": "Not found in context"} for q in questions]

    answers = parsed.get("answers")
    if not isinstance(answers, list):
        logger.warning("Batch response JSON missing answers list")
        return [{"question": q, "answer": "Not found in context"} for q in questions]

    mapping: Dict[str, str] = {}
    for item in answers:
        if not isinstance(item, dict):
            continue
        question_text = item.get("question")
        answer_text = _safe_text(
            item.get("answer") if isinstance(item.get("answer"), str) else None
        )
        if isinstance(question_text, str):
            mapping[question_text] = answer_text

    return [
        {"question": q, "answer": mapping.get(q, "Not found in context")}
        for q in questions
    ]


class AIClient:
    DEFAULT_PRIMARY_MODEL = "qwen/qwen3.6-plus:free"
    DEFAULT_FALLBACK_MODEL = "openai/gpt-4o"
    CIRCUIT_BREAKER_THRESHOLD = 3
    CIRCUIT_BREAKER_RESET_SECONDS = 300

    def __init__(
        self,
        api_key: str,
        base_url: str,
        primary_model: Optional[str] = None,
        fallback_model: Optional[str] = None,
        max_retries: int = 1,
        request_timeout: int = 30,
    ):
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.primary_model = primary_model or self.DEFAULT_PRIMARY_MODEL
        self.fallback_model = fallback_model or self.DEFAULT_FALLBACK_MODEL
        self.max_retries = max_retries
        self.request_timeout = request_timeout
        self.model_states: Dict[str, _ModelState] = {
            self.primary_model: _ModelState(),
            self.fallback_model: _ModelState(),
        }

    def _build_headers(self) -> Dict[str, str]:
        settings = get_settings()
        return {
            "HTTP-Referer": settings.OPENROUTER_HTTP_REFERER,
            "X-OpenRouter-Title": settings.OPENROUTER_TITLE,
        }

    def _is_model_disabled(self, model: str) -> bool:
        state = self.model_states.get(model)
        return state.is_disabled() if state else False

    def _mark_success(self, model: str) -> None:
        state = self.model_states.get(model)
        if state:
            state.record_success()

    def _mark_failure(self, model: str) -> None:
        state = self.model_states.get(model)
        if state:
            state.record_failure(
                self.CIRCUIT_BREAKER_THRESHOLD, self.CIRCUIT_BREAKER_RESET_SECONDS
            )

    def _call_model_batch(
        self,
        model: str,
        questions: List[str],
        context: str,
        max_tokens: int,
    ) -> Optional[List[Dict[str, str]]]:
        if self._is_model_disabled(model):
            logger.warning("Model %s is temporarily disabled by circuit breaker", model)
            return None

        payload = build_payload(model, questions, context, max_tokens)
        attempts = 0
        last_exception: Optional[Exception] = None

        while attempts <= self.max_retries:
            attempts += 1
            try:
                logger.info("Batch AI request attempt %d for model %s", attempts, model)
                logger.debug(
                    "Batch model %s request details: batch_size=%d, context_length=%d",
                    model,
                    len(questions),
                    len(context),
                )
                response = self.client.chat.completions.create(
                    extra_headers=self._build_headers(),
                    model=model,
                    timeout=self.request_timeout,
                    **payload,
                )
                result = _parse_batch_response(response, questions)
                if not result:
                    raise ValueError("Empty or invalid batch model response")
                self._mark_success(model)
                return result
            except Exception as exc:
                last_exception = exc
                logger.warning(
                    "Batch model %s attempt %d failed: %s", model, attempts, exc
                )
                if attempts > self.max_retries:
                    logger.exception(
                        "Batch model %s failed after %d attempts", model, attempts
                    )
                    self._mark_failure(model)
                else:
                    logger.info(
                        "Retrying batch model %s (attempt %d)", model, attempts + 1
                    )

        logger.debug("Last batch exception for model %s: %s", model, last_exception)
        return None

    def _call_model_batch_with_fallback(
        self,
        questions: List[str],
        context: str,
        max_tokens: int,
    ) -> Tuple[List[Dict[str, str]], str]:
        models_to_try = [self.primary_model]
        if self.fallback_model != self.primary_model:
            models_to_try.append(self.fallback_model)

        for model in models_to_try:
            if self._is_model_disabled(model):
                logger.warning("Skipping disabled model %s", model)
                continue

            result = self._call_model_batch(model, questions, context, max_tokens)
            if result is not None:
                return result, model

        fallback = [
            {"question": q, "answer": "Not found in context"} for q in questions
        ]
        return fallback, "none"

    def answer_questions(
        self,
        questions: List[str],
        context: str,
        max_tokens: int = 500,
        batch_size: int = 10,
        delay_seconds: float = 0.3,
    ) -> Tuple[List[Dict[str, str]], Dict[str, str]]:
        batched = batch_questions(questions, batch_size)
        answers: List[Dict[str, str]] = []
        model_map: Dict[str, str] = {}

        for batch_index, batch in enumerate(batched, start=1):
            start_time = time.monotonic()
            batch_result, model = self._call_model_batch_with_fallback(
                batch, context, max_tokens
            )
            elapsed = time.monotonic() - start_time
            logger.info(
                "Processed batch %d/%d with %d questions on model %s in %.2f seconds",
                batch_index,
                len(batched),
                len(batch),
                model,
                elapsed,
            )

            for entry in batch_result:
                answers.append(entry)
                model_map[entry["question"]] = model

            if batch_index < len(batched) and delay_seconds > 0:
                time.sleep(delay_seconds)

        return answers, model_map


def get_ai_client(model: Optional[str] = None) -> Optional[AIClient]:
    settings = get_settings()
    if not settings.OPENROUTER_API_KEY:
        logger.warning(
            "OPENROUTER_API_KEY not set in environment, AI features will be disabled"
        )
        return None

    key = model or settings.PRIMARY_MODEL
    if key not in _clients:
        _clients[key] = AIClient(
            api_key=settings.OPENROUTER_API_KEY,
            base_url=settings.OPENROUTER_API_BASE_URL,
            primary_model=key,
            fallback_model=settings.FALLBACK_MODEL,
            max_retries=1,
            request_timeout=settings.OPENROUTER_REQUEST_TIMEOUT,
        )
    return _clients[key]
