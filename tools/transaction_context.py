"""Application-owned authorization context for library transactions.

The CLI and LLM tools do not populate this context. An authenticated application
boundary must validate identity, permissions, confirmation, and policy first.
"""

from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Iterator


@dataclass(frozen=True)
class TrustedTransactionContext:
    actor_id: str
    member_id: int
    authorization_granted: bool
    confirmation_verified: bool
    loan_days: int
    max_active_loans: int

    def __post_init__(self) -> None:
        if not isinstance(self.actor_id, str) or not self.actor_id.strip():
            raise ValueError("actor_id must identify an authenticated application actor")
        if isinstance(self.member_id, bool) or not isinstance(self.member_id, int) or self.member_id <= 0:
            raise ValueError("member_id must be a positive authenticated member identifier")
        if self.authorization_granted is not True:
            raise ValueError("application authorization is required")
        if self.confirmation_verified is not True:
            raise ValueError("application-verified confirmation is required")
        if isinstance(self.loan_days, bool) or not isinstance(self.loan_days, int) or self.loan_days <= 0:
            raise ValueError("trusted loan_days must be a positive integer")
        if isinstance(self.max_active_loans, bool) or not isinstance(self.max_active_loans, int) or self.max_active_loans <= 0:
            raise ValueError("trusted max_active_loans must be a positive integer")


_current_context: ContextVar[TrustedTransactionContext | None] = ContextVar(
    "library_trusted_transaction_context", default=None
)


@contextmanager
def trusted_transaction_context(
    context: TrustedTransactionContext,
) -> Iterator[None]:
    """Set context for an application-authorized transaction call."""
    if not isinstance(context, TrustedTransactionContext):
        raise TypeError("context must be a TrustedTransactionContext")
    token: Token = _current_context.set(context)
    try:
        yield
    finally:
        _current_context.reset(token)


def get_trusted_transaction_context() -> TrustedTransactionContext:
    """Return trusted context or fail closed when no application set it."""
    context = _current_context.get()
    if context is None:
        raise RuntimeError("Giao dịch bị từ chối: chưa có xác thực từ tầng ứng dụng.")
    return context
