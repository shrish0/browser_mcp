import logging
from typing import Any, Callable, Dict, List, Optional

from openai import OpenAI

from setting import get_settings

logger = logging.getLogger(__name__)

# Type definitions for mapper functions
PayloadGenerator = Callable[[str, str, int], Dict[str, Any]]
ResponseParser = Callable[[Any], str]


def default_payload_generator(question: str, context: str, max_tokens: int) -> Dict[str, Any]:
    """Default payload generator for OpenAI-compatible models."""
    return {
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant that summarizes webpage content and answers questions based on the provided context.",
            },
            {
                "role": "user",
                "content": f"{question}\n\nContext:\n{context}",
            }
        ],
        "max_tokens": max_tokens,
    }


def default_response_parser(response: Any) -> str:
    """Default response parser for OpenAI-compatible models."""
    try:
        return response.choices[0].message.content
    except (AttributeError, IndexError) as e:
        logger.error(f"Failed to parse AI response: {e}")
        return "Error parsing AI response"


def custom_qwen_payload(question: str, context: str, max_tokens: int) -> Dict[str, Any]:
    """Custom payload generator for Qwen model."""
    # Example of model-specific logic: maybe Qwen performs better with a specific prompt structure
    return {
        "messages": [
            {
                "role": "system",
                "content": "You are an expert Qwen model specialized in extracting and summarizing information from web content.",
            },
            {
                "role": "user",
                "content": f"Please answer the following question based on the context provided.\n\nQuestion: {question}\n\nContext:\n{context}",
            }
        ],
        "max_tokens": max_tokens,
    }


def custom_qwen_parser(response: Any) -> str:
    """Custom response parser for Qwen model."""
    # Example of model-specific parsing logic
    try:
        content = response.choices[0].message.content
        # Maybe strip some specific artifacts if Qwen adds them
        return content.strip()
    except (AttributeError, IndexError) as e:
        logger.error(f"Failed to parse Qwen response: {e}")
        return "Error parsing Qwen response"


# Model configuration mapper
MODEL_MAPPERS: Dict[str, Dict[str, Any]] = {
    "default": {
        "payload_generator": default_payload_generator,
        "response_parser": default_response_parser,
    },
    "qwen/qwen3.6-plus:free": {
        "payload_generator": custom_qwen_payload,
        "response_parser": custom_qwen_parser,
    }
}

# Singleton instance
_client: Optional["AIClient"] = None


class AIClient:
    """Singleton AI client with fallback model support."""

    PRIMARY_MODEL = "qwen/qwen3.6-plus:free"
    FALLBACK_MODEL = "openai/gpt-4o"

    def __init__(self, api_key: str):
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
        self.primary_available = False
        self.fallback_available = False
        self._test_models()

    def _test_models(self) -> None:
        """Test both models with a small message to verify they work."""
        test_message = "test"
        dummy_context = "This is a test context"

        # Test primary model
        try:
            logger.info(f"Testing primary model: {self.PRIMARY_MODEL}")
            mapper = MODEL_MAPPERS.get(self.PRIMARY_MODEL, MODEL_MAPPERS["default"])
            payload = mapper["payload_generator"](test_message, dummy_context, 50)
            
            response = self.client.chat.completions.create(
                model=self.PRIMARY_MODEL,
                **payload
            )
            self.primary_available = True
            logger.info(f"Primary model {self.PRIMARY_MODEL} is available")
        except Exception as e:
            logger.warning(f"Primary model {self.PRIMARY_MODEL} failed: {e}")
            self.primary_available = False

        # Test fallback model
        try:
            logger.info(f"Testing fallback model: {self.FALLBACK_MODEL}")
            mapper = MODEL_MAPPERS.get(self.FALLBACK_MODEL, MODEL_MAPPERS["default"])
            payload = mapper["payload_generator"](test_message, dummy_context, 50)
            
            response = self.client.chat.completions.create(
                model=self.FALLBACK_MODEL,
                **payload
            )
            self.fallback_available = True
            logger.info(f"Fallback model {self.FALLBACK_MODEL} is available")
        except Exception as e:
            logger.warning(f"Fallback model {self.FALLBACK_MODEL} failed: {e}")
            self.fallback_available = False

        if not self.primary_available and not self.fallback_available:
            logger.error("Step 0: Model verification FAILED")
        elif self.primary_available:
            logger.info("Step 0: Primary model ready")
        else:
            logger.info("Step 0: Fallback model ready")

    def get_summary(
        self, 
        question: str, 
        context: str, 
        max_tokens: int = 500,
        return_model: bool = False
    ) -> str | tuple[str, str]:
        """Get AI summary with automatic fallback."""
        models_to_try = []

        if self.primary_available:
            models_to_try.append(self.PRIMARY_MODEL)
        if self.fallback_available:
            models_to_try.append(self.FALLBACK_MODEL)

        if not models_to_try:
            logger.error("No available models for summarization")
            err_msg = "AI summarization unavailable"
            return (err_msg, "none") if return_model else err_msg

        for model in models_to_try:
            try:
                logger.info(f"AI Step: Attempting with model: {model}")
                mapper = MODEL_MAPPERS.get(model, MODEL_MAPPERS["default"])
                payload = mapper["payload_generator"](question, context, max_tokens)
                
                completion = self.client.chat.completions.create(
                    extra_headers={
                        "HTTP-Referer": "",
                        "X-OpenRouter-Title": "Browser MCP",
                    },
                    model=model,
                    **payload
                )
                result = mapper["response_parser"](completion)
                logger.info(f"Successfully summarized with model: {model}")
                return (result, model) if return_model else result
            except Exception as e:
                logger.warning(f"Summarization failed with {model}: {e}")
                if model == models_to_try[-1]:
                    logger.exception(f"All models failed for summarization")
                continue

        err_msg = "AI summarization failed"
        return (err_msg, "none") if return_model else err_msg


def get_ai_client() -> AIClient:
    """Get singleton AI client instance."""
    global _client
    if _client is None:
        settings = get_settings()
        if not settings.OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY not set in environment")
        _client = AIClient(settings.OPENROUTER_API_KEY)
    return _client
