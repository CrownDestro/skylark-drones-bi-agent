"""
LLM abstraction layer with provider fallback chain.
Chain: Gemini → Groq → Deterministic fallback

Never exposes which provider was used in final responses.
"""
import logging
from typing import Optional

from backend.config import GEMINI_API_KEY, GROQ_API_KEY

logger = logging.getLogger(__name__)


class LLMRouter:
    """
    Routes LLM requests through the configured provider chain.
    If all LLM providers fail, returns None so the agent falls
    back to a deterministic structured response.
    """

    def __init__(self):
        self._providers = []
        self._init_providers()

    def _init_providers(self):
        if GEMINI_API_KEY:
            try:
                from backend.agent.providers.gemini import GeminiProvider
                self._providers.append(GeminiProvider(GEMINI_API_KEY))
                logger.info("Registered Gemini provider")
            except Exception as e:
                logger.warning("Failed to init Gemini: %s", e)

        if GROQ_API_KEY:
            try:
                from backend.agent.providers.groq import GroqProvider
                self._providers.append(GroqProvider(GROQ_API_KEY))
                logger.info("Registered Groq provider")
            except Exception as e:
                logger.warning("Failed to init Groq: %s", e)

        if not self._providers:
            logger.warning("No LLM providers configured. Will use deterministic fallback.")

    def generate(self, system_prompt: str, user_message: str, context: str = "") -> Optional[str]:
        """
        Try each provider in order. Return the first successful response.
        Returns None if all providers fail → caller uses deterministic fallback.
        """
        for provider in self._providers:
            if not provider.is_available():
                continue
            try:
                result = provider.generate(system_prompt, user_message, context)
                if result:
                    logger.info("LLM response from %s", type(provider).__name__)
                    return result
            except Exception as e:
                logger.warning("Provider %s failed: %s", type(provider).__name__, e)
                continue

        logger.warning("All LLM providers exhausted. Using deterministic fallback.")
        return None

    @property
    def has_providers(self) -> bool:
        return bool(self._providers)


# Singleton
_router: Optional[LLMRouter] = None


def get_router() -> LLMRouter:
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router
