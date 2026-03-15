"""Common LLM factory for creating ChatDeepSeek instances."""
from typing import Optional

from langchain_deepseek import ChatDeepSeek

from ..core.config import (
    DEEPSEEK_API_KEY,
    DETECTOR_TEMPERATURE,
    LLM_MAX_RETRIES,
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_TEMPERATURE,
    LLM_TIMEOUT,
)


def create_llm(
    temperature: Optional[float] = None,
    model: str = LLM_MODEL,
    api_key: Optional[str] = None,
) -> ChatDeepSeek:
    """
    Factory for creating ChatDeepSeek LLM instances.

    Args:
        temperature: Temperature for generation. If None, uses config default.
        model: Model name to use. Defaults to LLM_MODEL from config.
        api_key: Optional API key. If None, uses DEEPSEEK_API_KEY from config.

    Returns:
        Configured ChatDeepSeek instance.

    Raises:
        ValueError: If no API key is available.
    """
    key = api_key if api_key is not None else DEEPSEEK_API_KEY
    if key is None:
        raise ValueError("DEEPSEEK_API_KEY is not set")

    temp = temperature if temperature is not None else LLM_TEMPERATURE

    return ChatDeepSeek(
        model=model,
        temperature=temp,
        max_tokens=LLM_MAX_TOKENS,
        timeout=LLM_TIMEOUT,
        max_retries=LLM_MAX_RETRIES,
        api_key=key,
    )


def create_detector_llm() -> ChatDeepSeek:
    """
    Create an LLM instance optimized for hallucination detection.

    Uses DETECTOR_TEMPERATURE for more deterministic outputs.

    Returns:
        Configured ChatDeepSeek instance.
    """
    return create_llm(temperature=DETECTOR_TEMPERATURE)
