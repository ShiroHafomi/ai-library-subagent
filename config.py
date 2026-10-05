import os
from pathlib import Path

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"
POLICY_FILE = BASE_DIR / "data" / "policy.md"

load_dotenv(ENV_FILE, override=True)


def get_api_key() -> str:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Không tìm thấy GEMINI_API_KEY hoặc GOOGLE_API_KEY trong .env."
        )

    os.environ["GOOGLE_API_KEY"] = api_key
    return api_key


def get_model_name() -> str:
    # Có thể đổi trong .env mà không sửa code.
    return os.getenv("GEMINI_MODEL", "gemini-3.6-flash")


def create_model():
    return init_chat_model(
        get_model_name(),
        model_provider="google_genai",
        api_key=get_api_key(),
    )


def get_memory_user_id() -> str:
    """Get the user ID for memory operations."""
    return os.getenv("LIBRARY_USER_ID", "default-user")
