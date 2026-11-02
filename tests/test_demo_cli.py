import io
import os
import unittest
from contextlib import ExitStack, redirect_stdout
from unittest.mock import MagicMock, patch

from config import get_demo_member_id
from main import main
from tools.transaction_context import get_trusted_transaction_context


class DemoMemberConfigTests(unittest.TestCase):
    def test_parses_configured_member_id_as_positive_integer(self):
        with patch.dict(os.environ, {"DEMO_MEMBER_ID": "01"}, clear=False):
            self.assertEqual(get_demo_member_id(), 1)

    def test_missing_member_id_fails_closed(self):
        env = {key: value for key, value in os.environ.items() if key != "DEMO_MEMBER_ID"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(RuntimeError, "DEMO_MEMBER_ID"):
                get_demo_member_id()

    def test_non_numeric_or_non_positive_member_id_is_rejected(self):
        for value in ("abc", "0", "-1", "1.2", "2147483648", "١"):
            with patch.dict(os.environ, {"DEMO_MEMBER_ID": value}, clear=False):
                with self.subTest(value=value), self.assertRaisesRegex(ValueError, "DEMO_MEMBER_ID"):
                    get_demo_member_id()


class DemoCliContextTests(unittest.TestCase):
    def run_cli(self, inputs, member_id):
        agent = MagicMock()
        seen_contexts = []

        def invoke(*_args, **_kwargs):
            try:
                seen_contexts.append(get_trusted_transaction_context())
            except RuntimeError:
                seen_contexts.append(None)
            return {"messages": ["Tôi sẽ xử lý sách mã 9. [[CONFIRM_BORROW:9]]"]}

        agent.invoke.side_effect = invoke
        output = io.StringIO()
        with ExitStack() as stack:
            stack.enter_context(patch("main.initialize_database"))
            stack.enter_context(patch("main.create_model"))
            stack.enter_context(patch("main.create_library_agent", return_value=agent))
            stack.enter_context(patch("main.get_demo_member_id", return_value=member_id))
            stack.enter_context(patch("builtins.input", side_effect=[*inputs, "/exit"]))
            with redirect_stdout(output):
                main()

        with self.assertRaises(RuntimeError):
            get_trusted_transaction_context()
        return seen_contexts, output.getvalue()

    def test_demo_identity_is_scoped_to_agent_invocation(self):
        contexts, _output = self.run_cli(["Tôi muốn mượn Python Crash Course"], member_id=1)

        self.assertEqual(len(contexts), 1)
        self.assertEqual(contexts[0].member_id, 1)
        self.assertFalse(contexts[0].confirmation_verified)

    def test_cli_confirm_is_application_verified(self):
        contexts, output = self.run_cli(["Tôi muốn mượn sách mã 9", "/confirm"], member_id=1)

        self.assertIn("mã sách 9", output)
        self.assertEqual(len(contexts), 2)
        self.assertFalse(contexts[0].confirmation_verified)
        self.assertTrue(contexts[1].confirmation_verified)
        self.assertEqual(contexts[1].confirmed_action, "borrow")
        self.assertEqual(contexts[1].confirmed_resource_id, 9)

    def test_missing_demo_identity_does_not_create_transaction_context(self):
        contexts, _output = self.run_cli(["Tôi muốn trả sách"], member_id=None)

        self.assertEqual(contexts, [None])


if __name__ == "__main__":
    unittest.main()
