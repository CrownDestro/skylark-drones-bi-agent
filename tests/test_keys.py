"""Test both LLM providers directly."""
import sys, os
from dotenv import load_dotenv
load_dotenv()

print("Testing Groq...")
try:
    from backend.agent.providers.groq import GroqProvider
    groq = GroqProvider(os.environ["GROQ_API_KEY"])
    res = groq.generate("You are a helpful assistant", "Say the word 'Groq'")
    print(f"Groq Result: {res[:50]}")
except Exception as e:
    print(f"Groq Error: {e}")

print("\nTesting Gemini...")
try:
    from backend.agent.providers.gemini import GeminiProvider
    gem = GeminiProvider(os.environ["GEMINI_API_KEY"])
    res = gem.generate("You are a helpful assistant", "Say the word 'Gemini'", "Context: Test")
    print(f"Gemini Result: {res[:50]}")
except Exception as e:
    print(f"Gemini Error: {e}")
