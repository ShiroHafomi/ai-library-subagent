"""Tương thích ngược: SQL Book Agent được định nghĩa ở agents.book_agent."""
from agents.book_agent import BOOK_SYSTEM_PROMPT as SQL_SYSTEM_PROMPT
from agents.book_agent import create_book_subagent as create_sql_book_subagent
