import unittest
from unittest.mock import MagicMock, patch

from pydantic import ValidationError

from tools.borrow_tools import borrow_book
from tools.transaction_context import TrustedTransactionContext


class BorrowBookTests(unittest.TestCase):
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
        self.connection.cursor.return_value = self.cursor
        self.cursor.rowcount = 1

    @patch("tools.borrow_tools.get_connection")
    def test_missing_application_context_fails_before_database_connection(self, get_connection):
        result = borrow_book.invoke({"book_id": 9})

        self.assertIn("tầng ứng dụng", result)
        get_connection.assert_not_called()

    @patch("tools.borrow_tools.get_connection")
    @patch("tools.borrow_tools.get_trusted_transaction_context")
    def test_invalid_book_ids_are_rejected_before_database_connection(self, get_context, get_connection):
        get_context.return_value = self.context

        for book_id in (0, -1):
            with self.subTest(book_id=book_id):
                result = borrow_book.invoke({"book_id": book_id})
                self.assertIn("Mã sách không hợp lệ", result)

        for book_id in (True, "9", 9.0):
            with self.subTest(book_id=book_id):
                with self.assertRaises(ValidationError):
                    borrow_book.invoke({"book_id": book_id})

        self.assertIn("Mã sách không hợp lệ", borrow_book.func(True))
        get_connection.assert_not_called()

    @patch("tools.borrow_tools.get_connection")
    @patch("tools.borrow_tools.get_trusted_transaction_context")
    def test_success_commits_record_and_updates_book(self, get_context, get_connection):
        get_context.return_value = self.context
        get_connection.return_value = self.connection
        self.cursor.fetchone.side_effect = [
            {"id": 7, "name": "Thành viên thử nghiệm", "status": "active"},
            {"id": 9, "title": "Clean Code", "is_available": 1},
            {"active_count": 1},
        ]
        self.cursor.lastrowid = 42

        result = borrow_book.invoke({"book_id": 9})

        self.assertIn("Mượn sách thành công", result)
        self.assertIn("42", result)
        self.connection.commit.assert_called_once()
        self.connection.rollback.assert_not_called()
        sql_calls = [call.args[0] for call in self.cursor.execute.call_args_list]
        self.assertTrue(any("FOR UPDATE" in sql for sql in sql_calls))
        insert_call = next(call for call in self.cursor.execute.call_args_list if "INSERT INTO borrow_records" in call.args[0])
        self.assertEqual(insert_call.args[1][0], 7)
        self.assertEqual(insert_call.args[1][1], 9)

    @patch("tools.borrow_tools.get_connection")
    @patch("tools.borrow_tools.get_trusted_transaction_context")
    def test_missing_member_rolls_back_without_commit(self, get_context, get_connection):
        get_context.return_value = self.context
        get_connection.return_value = self.connection
        self.cursor.fetchone.return_value = None

        result = borrow_book.invoke({"book_id": 9})

        self.assertIn("Không tìm thấy thành viên", result)
        self.connection.rollback.assert_called_once()
        self.connection.commit.assert_not_called()

    @patch("tools.borrow_tools.get_connection")
    @patch("tools.borrow_tools.get_trusted_transaction_context")
    def test_unavailable_book_rolls_back_without_commit(self, get_context, get_connection):
        get_context.return_value = self.context
        get_connection.return_value = self.connection
        self.cursor.fetchone.side_effect = [
            {"id": 7, "name": "Thành viên thử nghiệm", "status": "active"},
            {"id": 9, "title": "Clean Code", "is_available": 0},
        ]

        result = borrow_book.invoke({"book_id": 9})

        self.assertIn("không thể mượn", result)
        self.connection.rollback.assert_called_once()
        self.connection.commit.assert_not_called()

    @patch("tools.borrow_tools.get_connection")
    @patch("tools.borrow_tools.get_trusted_transaction_context")
    def test_missing_book_rolls_back_without_commit(self, get_context, get_connection):
        get_context.return_value = self.context
        get_connection.return_value = self.connection
        self.cursor.fetchone.side_effect = [
            {"id": 7, "name": "Thành viên thử nghiệm", "status": "active"},
            None,
        ]

        result = borrow_book.invoke({"book_id": 9})

        self.assertIn("Không tìm thấy sách", result)
        self.connection.rollback.assert_called_once()
        self.connection.commit.assert_not_called()

    @patch("tools.borrow_tools.get_connection")
    @patch("tools.borrow_tools.get_trusted_transaction_context")
    def test_active_loan_limit_rolls_back_without_commit(self, get_context, get_connection):
        get_context.return_value = self.context
        get_connection.return_value = self.connection
        self.cursor.fetchone.side_effect = [
            {"id": 7, "name": "Thành viên thử nghiệm", "status": "active"},
            {"id": 9, "title": "Clean Code", "is_available": 1},
            {"active_count": self.context.max_active_loans},
        ]

        result = borrow_book.invoke({"book_id": 9})

        self.assertIn("đạt giới hạn mượn", result)
        self.connection.rollback.assert_called_once()
        self.connection.commit.assert_not_called()
        self.assertFalse(any("INSERT INTO borrow_records" in call.args[0] for call in self.cursor.execute.call_args_list))
        self.assertTrue(
            any(
                "member_id = %s AND status = 'borrowed'" in call.args[0]
                and call.args[1] == (self.context.member_id,)
                for call in self.cursor.execute.call_args_list
                if "COUNT(*)" in call.args[0]
            )
        )

    @patch("tools.borrow_tools.get_connection")
    @patch("tools.borrow_tools.get_trusted_transaction_context")
    def test_book_availability_update_failure_rolls_back_without_commit(self, get_context, get_connection):
        get_context.return_value = self.context
        get_connection.return_value = self.connection
        self.cursor.fetchone.side_effect = [
            {"id": 7, "name": "Thành viên thử nghiệm", "status": "active"},
            {"id": 9, "title": "Clean Code", "is_available": 1},
            {"active_count": 0},
        ]

        def fail_availability_update(sql, params=None):
            self.cursor.rowcount = 0 if "UPDATE books" in sql else 1

        self.cursor.execute.side_effect = fail_availability_update
        result = borrow_book.invoke({"book_id": 9})

        self.assertIn("giao dịch đã được hủy", result)
        self.connection.rollback.assert_called_once()
        self.connection.commit.assert_not_called()

    @patch("tools.borrow_tools.get_connection")
    @patch("tools.borrow_tools.get_trusted_transaction_context")
    def test_inactive_member_rolls_back_without_commit(self, get_context, get_connection):
        get_context.return_value = self.context
        get_connection.return_value = self.connection
        self.cursor.fetchone.return_value = {
            "id": 7,
            "name": "Thành viên thử nghiệm",
            "status": "inactive",
        }

        result = borrow_book.invoke({"book_id": 9})

        self.assertIn("không hoạt động", result)
        self.connection.rollback.assert_called_once()
        self.connection.commit.assert_not_called()

    @patch("tools.borrow_tools.get_connection")
    @patch("tools.borrow_tools.get_trusted_transaction_context")
    def test_insert_failure_rolls_back_and_never_reports_success(self, get_context, get_connection):
        get_context.return_value = self.context
        get_connection.return_value = self.connection
        self.cursor.fetchone.side_effect = [
            {"id": 7, "name": "Thành viên thử nghiệm", "status": "active"},
            {"id": 9, "title": "Clean Code", "is_available": 1},
            {"active_count": 0},
        ]

        def fail_insert(sql, params=None):
            if "INSERT INTO borrow_records" in sql:
                raise RuntimeError("simulated insert error")

        self.cursor.execute.side_effect = fail_insert
        with self.assertLogs("tools.borrow_tools", level="ERROR") as captured:
            result = borrow_book.invoke({"book_id": 9})

        self.assertTrue(any("simulated insert error" in message for message in captured.output))
        self.assertNotIn("Mượn sách thành công", result)
        self.connection.rollback.assert_called_once()
        self.connection.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
