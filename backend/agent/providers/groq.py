"""
LLM provider: Groq (free tier fallback).
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class GroqProvider:
    # Confirmed working models on Groq
    MODEL = "groq/compound"
    MODEL_FALLBACK = "qwen/qwen3.6-27b"

    def __init__(self, api_key: str):
        self._key = api_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            from groq import Groq  # type: ignore
            self._client = Groq(api_key=self._key)
        return self._client

    def generate(self, system_prompt: str, user_message: str, context: str = "") -> Optional[str]:
        """
        Generate a response from Groq.
        Returns None on failure.
        """
        try:
            client = self._get_client()
            messages = [
                {"role": "system", "content": system_prompt},
            ]
            if context:
                messages.append({"role": "user", "content": f"Business data context:\n{context}"})
                messages.append({"role": "assistant", "content": "I have reviewed the business data. Please ask your question."})
            messages.append({"role": "user", "content": user_message})

            for model in (self.MODEL, self.MODEL_FALLBACK):
                try:
                    completion = client.chat.completions.create(
                        model=model,
                        messages=messages,
                        max_tokens=1500,
                        temperature=0.3,
                    )
                    text = completion.choices[0].message.content or ""
                    # Discard error-shaped responses (e.g. JSON error dicts)
                    if text.strip().startswith("{'error'") or text.strip().startswith('{"error"'):
                        logger.warning("Groq returned error-shaped response for model %s, skipping", model)
                        continue
                    if text.strip():
                        logger.info("Groq success (model=%s)", model)
                        return text
                except Exception as e:
                    logger.warning("Groq model %s failed: %s", model, e)
                    continue
            return None
        except Exception as e:
            logger.warning("Groq generation failed: %s", e)
            return None

    def is_available(self) -> bool:
        return bool(self._key)
