import unittest
from unittest.mock import MagicMock, patch

from agents.main_agent import create_library_agent
from agents.borrow_agent import BORROW_SYSTEM_PROMPT, create_borrow_subagent
from agents.policy_agent import POLICY_SUBAGENT
from agents.return_agent import RETURN_SUBAGENT
from tools.policy_agent import answer_policy
from tools.borrow_tools import borrow_book
from tools.return_tools import find_active_loans, return_book
from tools.memory_tools import read_memory, save_memory


class MainAgentTests(unittest.TestCase):
    @patch('agents.main_agent.create_deep_agent')
    @patch('agents.main_agent.create_borrow_subagent')
    @patch('agents.main_agent.create_book_subagent')
    @patch('agents.main_agent.create_book_sql_tools')
    def test_create_library_agent_shares_readonly_book_tools_with_borrow_agent(
        self,
        mock_create_book_sql_tools,
        mock_create_book_subagent,
        mock_create_borrow_subagent,
        mock_create_deep_agent,
    ):
        mock_agent = MagicMock()
        mock_create_deep_agent.return_value = mock_agent
        book_tools = [MagicMock(name='sql_db_query'), MagicMock(name='sql_db_schema')]
        mock_create_book_sql_tools.return_value = book_tools
        book_subagent = {'name': 'book-agent', 'tools': book_tools}
        borrow_subagent = {'name': 'borrow-agent', 'tools': [*book_tools, borrow_book]}
        mock_create_book_subagent.return_value = book_subagent
        mock_create_borrow_subagent.return_value = borrow_subagent
        mock_model = MagicMock()

        agent = create_library_agent(mock_model)

        mock_create_book_sql_tools.assert_called_once_with(mock_model)
        mock_create_book_subagent.assert_called_once_with(book_tools)
        mock_create_borrow_subagent.assert_called_once_with(book_tools)
        mock_create_deep_agent.assert_called_once()
        _, kwargs = mock_create_deep_agent.call_args
        self.assertIs(kwargs['model'], mock_model)
        self.assertEqual(kwargs['tools'], [read_memory, save_memory])
        self.assertEqual(
            kwargs['subagents'],
            [book_subagent, POLICY_SUBAGENT, borrow_subagent, RETURN_SUBAGENT],
        )
        self.assertEqual(POLICY_SUBAGENT['tools'], [answer_policy])
        self.assertEqual(borrow_subagent['tools'], [*book_tools, borrow_book])
        self.assertEqual(RETURN_SUBAGENT['tools'], [find_active_loans, return_book])
        self.assertTrue(kwargs['system_prompt'].startswith('Bạn là Main Agent'))
        self.assertIn('Giao các yêu cầu mượn sách cho borrow-agent', kwargs['system_prompt'])
        self.assertIn('Giao các yêu cầu trả sách cho return-agent', kwargs['system_prompt'])
        self.assertIn('Chỉ thông báo thành công khi công cụ xác nhận giao dịch đã COMMIT', kwargs['system_prompt'])
        self.assertEqual(set(borrow_book.args), {'book_id'})
        self.assertEqual(set(return_book.args), {'record_id'})
        self.assertIsNotNone(kwargs['checkpointer'])
        self.assertIs(agent, mock_agent)

    def test_borrow_subagent_gets_catalog_reads_and_guarded_transaction_tool(self):
        sql_tools = [MagicMock(name='sql_db_query'), MagicMock(name='sql_db_schema')]

        subagent = create_borrow_subagent(sql_tools)

        self.assertEqual(subagent['tools'], [*sql_tools, borrow_book])
        self.assertIn('sql_db_query_checker', BORROW_SYSTEM_PROMPT)
        self.assertIn('SELECT chỉ trên books', BORROW_SYSTEM_PROMPT)
        self.assertIn('khóa và kiểm tra lại sách', BORROW_SYSTEM_PROMPT)


if __name__ == '__main__':
    unittest.main()
