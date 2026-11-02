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
    confirmed_action: str | None = None
    confirmed_resource_id: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.actor_id, str) or not self.actor_id.strip():
            raise ValueError("actor_id must identify an authenticated application actor")
        if isinstance(self.member_id, bool) or not isinstance(self.member_id, int) or self.member_id <= 0:
            raise ValueError("member_id must be a positive authenticated member identifier")
        if self.authorization_granted is not True:
            raise ValueError("application authorization is required")
        if not isinstance(self.confirmation_verified, bool):
            raise ValueError("confirmation_verified must be an application boolean")
        if self.confirmation_verified:
            if self.confirmed_action not in {"borrow", "return"}:
                raise ValueError("confirmed action must be borrow or return")
            if (
                isinstance(self.confirmed_resource_id, bool)
                or not isinstance(self.confirmed_resource_id, int)
                or self.confirmed_resource_id <= 0
            ):
                raise ValueError("confirmed resource ID must be a positive integer")
        elif self.confirmed_action is not None or self.confirmed_resource_id is not None:
            raise ValueError("unconfirmed context cannot contain a confirmed target")
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


def get_trusted_transaction_context(
    *, require_confirmation: bool = False
) -> TrustedTransactionContext:
    """Return trusted context or fail closed when no application set it."""
    context = _current_context.get()
    if context is None:
        raise RuntimeError("Giao dịch bị từ chối: chưa có xác thực từ tầng ứng dụng.")
    if require_confirmation and not context.confirmation_verified:
        raise RuntimeError("Giao dịch bị từ chối: cần xác nhận rõ ràng từ CLI.")
    return context
