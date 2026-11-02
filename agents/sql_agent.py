"""Tương thích ngược: SQL Book Agent được định nghĩa ở agents.book_agent."""
from agents.book_agent import BOOK_SYSTEM_PROMPT as SQL_SYSTEM_PROMPT
from agents.book_agent import create_book_subagent
from tools.book_tools import create_book_sql_tools

__all__ = ["SQL_SYSTEM_PROMPT", "create_sql_book_subagent"]


def create_sql_book_subagent(model):
    """Preserve the legacy model-based factory API."""
    return create_book_subagent(create_book_sql_tools(model))
