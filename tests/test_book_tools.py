import unittest
from unittest.mock import MagicMock, patch

from tools.book_tools import search_books


class SearchBooksTests(unittest.TestCase):
    @patch("tools.book_tools.get_connection")
    def test_keyword_and_status_are_parameterized_against_actual_columns(self, get_connection):
        connection = MagicMock()
        cursor = MagicMock()
        connection.cursor.return_value = cursor
        cursor.fetchall.return_value = [
            {"id": 5, "title": "Clean Code", "author": "Robert Martin", "category": "Software", "is_available": 1}
        ]
        get_connection.return_value = connection

        result = search_books.invoke({"keyword": "Clean", "status": "available"})

        self.assertIn("Clean Code", result)
        sql, params = cursor.execute.call_args.args
        self.assertIn("title", sql)
        self.assertIn("author", sql)
        self.assertIn("is_available", sql)
        self.assertNotIn("Clean", sql)
        self.assertEqual(params, ["%Clean%", "%Clean%"])
        cursor.close.assert_called_once()
        connection.close.assert_called_once()

    @patch("tools.book_tools.get_connection")
    def test_sql_metacharacters_remain_bound_search_data(self, get_connection):
        connection = MagicMock()
        cursor = MagicMock()
        connection.cursor.return_value = cursor
        cursor.fetchall.return_value = []
        get_connection.return_value = connection
        keyword = "%' OR 1=1 --"

        result = search_books.invoke({"keyword": keyword})

        sql, params = cursor.execute.call_args.args
        self.assertNotIn(keyword, sql)
        self.assertEqual(params, [f"%{keyword}%", f"%{keyword}%"])
        self.assertEqual(result, "Không tìm thấy sách phù hợp.")

    @patch("tools.book_tools.get_connection")
    def test_rejects_unknown_status_without_database_connection(self, get_connection):
        result = search_books.invoke({"status": "lost"})

        self.assertIn("Trạng thái không hợp lệ", result)
        get_connection.assert_not_called()


if __name__ == "__main__":
    unittest.main()
