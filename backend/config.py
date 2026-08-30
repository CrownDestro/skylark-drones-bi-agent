"""
Central configuration — reads from environment variables.
Never hardcodes secrets.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Monday.com
MONDAY_API_TOKEN: str = os.environ.get("MONDAY_API_TOKEN", "")
DEALS_BOARD_ID: str = os.environ.get("DEALS_BOARD_ID", "5030966894")
WORK_ORDERS_BOARD_ID: str = os.environ.get("WORK_ORDERS_BOARD_ID", "5030966898")
MONDAY_API_URL: str = "https://api.monday.com/v2"

# LLM Providers
GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
GROQ_API_KEY: str = os.environ.get("GROQ_API_KEY", "")
HF_TOKEN: str = os.environ.get("HF_TOKEN", "")

# CORS
FRONTEND_URL: str = os.environ.get("FRONTEND_URL", "http://localhost:3000")

# Closure Probability weight mapping
# Assumption: Qualitative values mapped to numeric weights for weighted pipeline.
# Documented in DECISION_LOG.md.
PROBABILITY_WEIGHTS = {
    "high": 0.80,
    "medium": 0.50,
    "low": 0.20,
    "": 0.30,   # unknown → conservative estimate
}

# Current quarter helper is in utils; this file is config only.
