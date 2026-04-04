import logging
import time
from typing import Any, Dict, Optional, Tuple, Union

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


def build_payload(model: str, question: str, context: str, max_tokens: int) -> Dict[str, Any]:
    prompt_key = MODEL_CONFIG.get(model, "default")
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
            state.record_failure(self.CIRCUIT_BREAKER_THRESHOLD, self.CIRCUIT_BREAKER_RESET_SECONDS)

    def _call_model(self, model: str, question: str, context: str, max_tokens: int) -> Optional[str]:
        if self._is_model_disabled(model):
            logger.warning("Model %s is temporarily disabled by circuit breaker", model)
            return None

        payload = build_payload(model, question, context, max_tokens)
        attempts = 0
        last_exception: Optional[Exception] = None

        while attempts <= self.max_retries:
            attempts += 1
            try:
                logger.info("AI request attempt %d for model %s", attempts, model)
                logger.debug(
                    "Model %s request details: question_length=%d, context_length=%d",
                    model,
                    len(question),
                    len(context),
                )
                response = self.client.chat.completions.create(
                    extra_headers=self._build_headers(),
                    model=model,
                    timeout=self.request_timeout,
                    **payload,
                )
                result = _parse_response(response)
                if not result or result == "Not found in context":
                    raise ValueError("Empty or invalid model response")
                self._mark_success(model)
                return result
            except Exception as exc:
                last_exception = exc
                logger.warning("Model %s attempt %d failed: %s", model, attempts, exc)
                if attempts > self.max_retries:
                    logger.exception("Model %s failed after %d attempts", model, attempts)
                    self._mark_failure(model)
                else:
                    logger.info("Retrying model %s (attempt %d)", model, attempts + 1)

        logger.debug("Last exception for model %s: %s", model, last_exception)
        return None

    def get_summary(
        self,
        question: str,
        context: str,
        max_tokens: int = 500,
        return_model: bool = False,
    ) -> Union[str, Tuple[str, str]]:
        models_to_try = [self.primary_model]
        if self.fallback_model != self.primary_model:
            models_to_try.append(self.fallback_model)

        for model in models_to_try:
            if self._is_model_disabled(model):
                logger.warning("Skipping disabled model %s", model)
                continue

            result = self._call_model(model, question, context, max_tokens)
            if result is not None:
                return (result, model) if return_model else result

        err_msg = "AI summarization failed"
        return (err_msg, "none") if return_model else err_msg


def get_ai_client(model: Optional[str] = None) -> AIClient:
    settings = get_settings()
    if not settings.OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY not set in environment")

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

