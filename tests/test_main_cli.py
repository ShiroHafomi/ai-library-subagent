import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

from main import main


class MainCliTests(unittest.TestCase):
    @patch('main.initialize_database')
    @patch('main.create_model')
    @patch('main.create_library_agent')
    @patch('builtins.input', side_effect=['hello', '/exit'])
    def test_agent_exception_is_not_exposed_to_cli_user(
        self, _input, create_agent, _create_model, _initialize_database
    ):
        agent = MagicMock()
        agent.invoke.side_effect = RuntimeError('database password=secret')
        create_agent.return_value = agent
        output = io.StringIO()

        with redirect_stdout(output):
            main()

        text = output.getvalue()
        self.assertIn('DEMO_MEMBER_ID không phải xác thực nhiều người dùng', text)
        self.assertIn('Đã xảy ra lỗi khi xử lý yêu cầu', text)
        self.assertNotIn('database password=secret', text)
        agent.invoke.assert_called_once()


if __name__ == '__main__':
    unittest.main()
