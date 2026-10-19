import os
from dotenv import load_dotenv

# Load variables from .env if present
load_dotenv()

# Default Gemini model
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Available Gemini models
AVAILABLE_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
]

# Scoring Profiles
PROFILE_BLACKFOLD = "blackfold"
PROFILE_GENERAL = "general"

DEFAULT_PROFILE = os.getenv("SCORING_PROFILE", PROFILE_BLACKFOLD)
AVAILABLE_PROFILES = [PROFILE_BLACKFOLD, PROFILE_GENERAL]

# Batch size limit for safety & rate limits
MAX_LEADS_PER_BATCH = 100

def get_api_key() -> str:
    """Retrieve Gemini API key from environment variable."""
    return os.getenv("GEMINI_API_KEY", "").strip()
