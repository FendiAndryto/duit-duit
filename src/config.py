import os
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

def get_api_key(override_key: str = None) -> str:
    """
    Retrieves the Gemini API Key.
    Prioritizes the override_key (e.g., from Streamlit UI),
    otherwise falls back to the GEMINI_API_KEY from environment variables.
    
    Raises:
        ValueError: If API Key is not found in either source.
    """
    if override_key:
        return override_key
    
    env_key = os.getenv("GEMINI_API_KEY")
    if not env_key:
        raise ValueError(
            "GEMINI_API_KEY tidak ditemukan. "
            "Pastikan Anda telah mengatur environment variable atau memasukkannya via Sidebar UI."
        )
        
    return env_key
