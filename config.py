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
        max_output_tokens=512,
        # Deep Agents summarizes older history at 85% of this operational budget
        # and retains the recent 10%; this is not a provider context limit.
        profile={"max_input_tokens": 24_000},
    )


def get_demo_member_id() -> int:
    """Return the configured local demo member ID or fail closed."""
    value = os.getenv("DEMO_MEMBER_ID", "").strip()
    if not value:
        raise RuntimeError(
            "Thiếu DEMO_MEMBER_ID trong .env; chưa thể thực hiện mượn/trả sách."
        )
    if not value.isascii() or not value.isdecimal():
        raise ValueError("DEMO_MEMBER_ID phải là số nguyên dương.")

    member_id = int(value)
    if member_id <= 0 or member_id > 2_147_483_647:
        raise ValueError("DEMO_MEMBER_ID phải nằm trong phạm vi INT dương của MySQL.")
    return member_id


def get_memory_user_id() -> str:
    """Get the user ID for memory operations."""
    user_id = os.getenv("LIBRARY_USER_ID", "").strip()
    if not user_id or user_id == "default-user":
        raise RuntimeError("Long-term memory bị từ chối: cần LIBRARY_USER_ID riêng cho người dùng đã xác thực.")
    return user_id
