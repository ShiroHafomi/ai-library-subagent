import unittest

from langgraph.pregel._executor import BackgroundExecutor

from tools.transaction_context import (
    TrustedTransactionContext,
    get_trusted_transaction_context,
    trusted_transaction_context,
)


class TrustedTransactionContextTests(unittest.TestCase):
    def make_context(self, **overrides):
        values = {
            "actor_id": "actor-123",
            "member_id": 7,
            "authorization_granted": True,
            "confirmation_verified": True,
            "loan_days": 14,
            "confirmed_action": "borrow",
            "confirmed_resource_id": 9,
            "max_active_loans": 3,
        }
        values.update(overrides)
        return TrustedTransactionContext(**values)

    def test_context_is_unavailable_outside_application_scope(self):
        with self.assertRaises(RuntimeError):
            get_trusted_transaction_context()

    def test_context_is_available_only_inside_scope(self):
        context = self.make_context()

        with trusted_transaction_context(context):
            self.assertIs(get_trusted_transaction_context(), context)

        with self.assertRaises(RuntimeError):
            get_trusted_transaction_context()

    def test_langgraph_background_executor_propagates_trusted_context(self):
        context = self.make_context()

        with trusted_transaction_context(context):
            with BackgroundExecutor({}) as submit:
                future = submit(get_trusted_transaction_context)
                self.assertIs(future.result(timeout=5), context)

        with self.assertRaises(RuntimeError):
            get_trusted_transaction_context()

    def test_nested_scope_restores_outer_context(self):
        outer = self.make_context(actor_id="outer")
        inner = self.make_context(actor_id="inner")

        with trusted_transaction_context(outer):
            with trusted_transaction_context(inner):
                self.assertIs(get_trusted_transaction_context(), inner)
            self.assertIs(get_trusted_transaction_context(), outer)

    def test_rejects_untrusted_or_invalid_authorization_values(self):
        for field, value in (
            ("actor_id", " "),
            ("member_id", 0),
            ("authorization_granted", False),
            ("confirmation_verified", False),
            ("loan_days", 0),
            ("max_active_loans", 0),
        ):
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.make_context(**{field: value})


if __name__ == "__main__":
    unittest.main()
