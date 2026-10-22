import unittest
from unittest.mock import MagicMock, patch

from pydantic import ValidationError

from tools.return_tools import return_book
from tools.transaction_context import TrustedTransactionContext


class ReturnBookTests(unittest.TestCase):
    def setUp(self):
        self.context = TrustedTransactionContext(
            actor_id="actor-test",
            member_id=7,
            authorization_granted=True,
            confirmation_verified=True,
            loan_days=14,
            max_active_loans=3,
        )
        self.connection = MagicMock()
        self.cursor = MagicMock()
        self.cursor.rowcount = 1
        self.connection.cursor.return_value = self.cursor

    @patch("tools.return_tools.get_connection")
    def test_missing_application_context_fails_before_database_connection(self, get_connection):
        result = return_book.invoke({"record_id": 42})

        self.assertIn("tầng ứng dụng", result)
        get_connection.assert_not_called()

    @patch("tools.return_tools.get_connection")
    @patch("tools.return_tools.get_trusted_transaction_context")
    def test_invalid_record_ids_are_rejected_before_database_connection(self, get_context, get_connection):
        get_context.return_value = self.context

        for record_id in (0, -1):
            with self.subTest(record_id=record_id):
                result = return_book.invoke({"record_id": record_id})
                self.assertIn("Mã phiếu mượn không hợp lệ", result)

        for record_id in (True, "9", 9.0):
            with self.subTest(record_id=record_id):
                with self.assertRaises(ValidationError):
                    return_book.invoke({"record_id": record_id})

        self.assertIn("Mã phiếu mượn không hợp lệ", return_book.func(True))
        get_connection.assert_not_called()

    @patch("tools.return_tools.get_connection")
    @patch("tools.return_tools.get_trusted_transaction_context")
    def test_success_updates_record_and_recomputes_book_availability(self, get_context, get_connection):
        get_context.return_value = self.context
        get_connection.return_value = self.connection
        self.cursor.fetchone.side_effect = [
            {"id": 42, "member_id": 7, "book_id": 9, "status": "borrowed"},
            {"id": 9, "title": "Clean Code"},
            {"active_count": 0},
        ]

        result = return_book.invoke({"record_id": 42})

        self.assertIn("Trả sách thành công", result)
        self.connection.commit.assert_called_once()
        self.connection.rollback.assert_not_called()
        sql_calls = [call.args[0] for call in self.cursor.execute.call_args_list]
        self.assertTrue(any("FOR UPDATE" in sql for sql in sql_calls))
        self.assertTrue(any("status = 'borrowed'" in sql for sql in sql_calls))
        availability_call = next(call for call in self.cursor.execute.call_args_list if "UPDATE books" in call.args[0])
        self.assertEqual(availability_call.args[1][0], 1)

    @patch("tools.return_tools.get_connection")
    @patch("tools.return_tools.get_trusted_transaction_context")
    def test_record_owned_by_another_member_is_rejected(self, get_context, get_connection):
        get_context.return_value = self.context
        get_connection.return_value = self.connection
        self.cursor.fetchone.return_value = {
            "id": 42,
            "member_id": 8,
            "book_id": 9,
            "status": "borrowed",
        }

        result = return_book.invoke({"record_id": 42})

        self.assertIn("quyền", result)
        self.connection.rollback.assert_called_once()
        self.connection.commit.assert_not_called()

    @patch("tools.return_tools.get_connection")
    @patch("tools.return_tools.get_trusted_transaction_context")
    def test_already_returned_record_is_rejected(self, get_context, get_connection):
        get_context.return_value = self.context
        get_connection.return_value = self.connection
        self.cursor.fetchone.return_value = {
            "id": 42,
            "member_id": 7,
            "book_id": 9,
            "status": "returned",
        }

        result = return_book.invoke({"record_id": 42})

        self.assertIn("đã được trả", result)
        self.connection.rollback.assert_called_once()
        self.connection.commit.assert_not_called()

    @patch("tools.return_tools.get_connection")
    @patch("tools.return_tools.get_trusted_transaction_context")
    def test_noop_availability_update_is_valid_when_another_loan_remains(self, get_context, get_connection):
        get_context.return_value = self.context
        get_connection.return_value = self.connection
        self.cursor.fetchone.side_effect = [
            {"id": 42, "member_id": 7, "book_id": 9, "status": "borrowed"},
            {"id": 9, "title": "Clean Code"},
            {"active_count": 1},
        ]

        def set_rowcount(sql, params=None):
            self.cursor.rowcount = 1 if "UPDATE borrow_records" in sql else 0

        self.cursor.execute.side_effect = set_rowcount
        result = return_book.invoke({"record_id": 42})

        self.assertIn("Trả sách thành công", result)
        self.connection.commit.assert_called_once()
        count_call = next(call for call in self.cursor.execute.call_args_list if "COUNT(*)" in call.args[0])
        self.assertIn("book_id = %s AND status = 'borrowed'", count_call.args[0])
        self.assertEqual(count_call.args[1], (9,))
        availability_call = next(call for call in self.cursor.execute.call_args_list if "UPDATE books" in call.args[0])
        self.assertEqual(availability_call.args[1], (0, 9))

    @patch("tools.return_tools.get_connection")
    @patch("tools.return_tools.get_trusted_transaction_context")
    def test_update_failure_rolls_back_and_never_reports_success(self, get_context, get_connection):
        get_context.return_value = self.context
        get_connection.return_value = self.connection
        self.cursor.fetchone.side_effect = [
            {"id": 42, "member_id": 7, "book_id": 9, "status": "borrowed"},
            {"id": 9, "title": "Clean Code"},
        ]
        self.cursor.rowcount = 0

        result = return_book.invoke({"record_id": 42})

        self.assertNotIn("Trả sách thành công", result)
        self.connection.rollback.assert_called_once()
        self.connection.commit.assert_not_called()

    @patch("tools.return_tools.get_connection")
    @patch("tools.return_tools.get_trusted_transaction_context")
    def test_missing_record_rolls_back_without_commit(self, get_context, get_connection):
        get_context.return_value = self.context
        get_connection.return_value = self.connection
        self.cursor.fetchone.return_value = None

        result = return_book.invoke({"record_id": 42})

        self.assertIn("Không tìm thấy phiếu mượn", result)
        self.connection.rollback.assert_called_once()
        self.connection.commit.assert_not_called()

    @patch("tools.return_tools.get_connection")
    @patch("tools.return_tools.get_trusted_transaction_context")
    def test_non_borrowed_record_rolls_back_without_commit(self, get_context, get_connection):
        get_context.return_value = self.context
        get_connection.return_value = self.connection
        self.cursor.fetchone.return_value = {
            "id": 42,
            "member_id": 7,
            "book_id": 9,
            "status": "cancelled",
        }

        result = return_book.invoke({"record_id": 42})

        self.assertIn("không ở trạng thái đang mượn", result)
        self.connection.rollback.assert_called_once()
        self.connection.commit.assert_not_called()

    @patch("tools.return_tools.get_connection")
    @patch("tools.return_tools.get_trusted_transaction_context")
    def test_missing_book_rolls_back_without_commit(self, get_context, get_connection):
        get_context.return_value = self.context
        get_connection.return_value = self.connection
        self.cursor.fetchone.side_effect = [
            {"id": 42, "member_id": 7, "book_id": 9, "status": "borrowed"},
            None,
        ]

        result = return_book.invoke({"record_id": 42})

        self.assertIn("Không tìm thấy sách tương ứng", result)
        self.connection.rollback.assert_called_once()
        self.connection.commit.assert_not_called()

    @patch("tools.return_tools.get_connection")
    @patch("tools.return_tools.get_trusted_transaction_context")
    def test_database_exception_rolls_back_and_never_reports_success(self, get_context, get_connection):
        get_context.return_value = self.context
        get_connection.return_value = self.connection
        self.cursor.fetchone.side_effect = [
            {"id": 42, "member_id": 7, "book_id": 9, "status": "borrowed"},
            {"id": 9, "title": "Clean Code"},
        ]

        def fail_record_update(sql, params=None):
            if "UPDATE borrow_records" in sql:
                raise RuntimeError("simulated database error")

        self.cursor.execute.side_effect = fail_record_update
        with self.assertLogs("tools.return_tools", level="ERROR") as captured:
            result = return_book.invoke({"record_id": 42})

        self.assertTrue(any("simulated database error" in message for message in captured.output))
        self.assertIn("giao dịch không thành công", result)
        self.connection.rollback.assert_called_once()
        self.connection.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
