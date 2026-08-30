"""
LLM provider: Google Gemini via google-genai SDK.

Uses the new google.genai.Client which supports AQ.* API keys
from Google AI Studio (https://aistudio.google.com/apikey).

Falls back gracefully on any error so the deterministic response
always works as a last resort.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Model priority list — first available is used
GEMINI_MODELS = [
    "gemini-3.6-flash",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-flash-latest",
]


class GeminiProvider:

    def __init__(self, api_key: str):
        self._key = api_key
        self._client = None
        self._working_model: Optional[str] = None  # cached after first success

    def _get_client(self):
        if self._client is None:
            from google import genai  # type: ignore
            self._client = genai.Client(api_key=self._key)
            logger.info("Gemini client initialised (google-genai SDK)")
        return self._client

    def generate(self, system_prompt: str, user_message: str, context: str = "") -> Optional[str]:
        """
        Generate an executive-language response from Gemini.
        All numbers come from the deterministic context — LLM only produces prose.
        Returns None on failure (caller uses deterministic fallback).
        """
        full_prompt = (
            f"{system_prompt}\n\n"
            f"{context}\n\n"
            f"User question: {user_message}\n\n"
            "Provide a concise, executive-level answer using ONLY the data above. "
            "Never invent numbers. Use ₹ for all monetary values. "
            "Format with markdown headers and bullet points. "
            "Keep the response under 400 words."
        )

        try:
            client = self._get_client()

            # If we already know a working model, use it directly
            if self._working_model:
                return self._try_model(client, self._working_model, full_prompt)

            # Try each model until one works
            for model in GEMINI_MODELS:
                result = self._try_model(client, model, full_prompt)
                if result:
                    self._working_model = model  # cache for next call
                    return result

            logger.warning("All Gemini models exhausted — no response")
            return None

        except Exception as e:
            err = str(e)
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                logger.warning("Gemini provider hit rate limit. Fast-failing to next provider.")
                return None
            logger.warning("Gemini provider error: %s: %s", type(e).__name__, e)
            return None

    def _try_model(self, client, model: str, prompt: str) -> Optional[str]:
        """Attempt one Gemini model. Returns text or None."""
        try:
            from google.genai import types  # type: ignore
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=1024,
                    system_instruction=None,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
                ),
            )
            text = response.text if hasattr(response, "text") else ""
            if text and text.strip():
                logger.info("Gemini success (model=%s, chars=%d)", model, len(text))
                return text.strip()
        except Exception as e:
            err = str(e)
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                logger.warning("Gemini model %s rate limited (429). Failing fast to fallback.", model)
                raise  # Re-raise to break the model loop immediately
            elif "not found" in err.lower() or "deprecated" in err.lower() or "not supported" in err.lower():
                logger.warning("Gemini model %s unavailable: %s", model, err[:120])
            else:
                logger.warning("Gemini model %s error: %s: %s", model, type(e).__name__, err[:120])
        return None

    def is_available(self) -> bool:
        return bool(self._key)
