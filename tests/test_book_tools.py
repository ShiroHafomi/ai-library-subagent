import unittest
from unittest.mock import patch

from sqlalchemy import Boolean, Integer, String

from tools.book_tools import create_book_sql_tools


class BookSQLToolsTests(unittest.TestCase):
    @patch.dict('os.environ', {}, clear=True)
    def test_requires_dedicated_readonly_credentials(self):
        with self.assertRaisesRegex(RuntimeError, 'DB_READONLY_USER'):
            create_book_sql_tools(object())

    @patch('tools.book_tools.SQLDatabaseToolkit')
    @patch('tools.book_tools.SQLDatabase')
    @patch('tools.book_tools.inspect')
    @patch('tools.book_tools.create_engine')
    @patch.dict(
        'os.environ',
        {
            'DB_READONLY_USER': 'reader',
            'DB_READONLY_PASSWORD': 'reader-password',
            'DB_HOST': 'localhost',
            'DB_PORT': '3306',
            'DB_NAME': 'library',
        },
        clear=True,
    )
    def test_exposes_sql_toolkit_only_after_books_schema_reflection(
        self, create_engine, inspect, sql_database, toolkit
    ):
        engine = create_engine.return_value
        inspector = inspect.return_value
        inspector.get_pk_constraint.return_value = {'constrained_columns': ['id']}
        inspector.get_columns.return_value = [
            {'name': 'id', 'type': Integer(), 'nullable': False},
            {'name': 'title', 'type': String(255), 'nullable': False},
            {'name': 'author', 'type': String(255), 'nullable': False},
            {'name': 'category', 'type': String(255), 'nullable': False},
            {'name': 'is_available', 'type': Boolean(), 'nullable': False},
        ]
        expected_tools = [object()]
        toolkit.return_value.get_tools.return_value = expected_tools

        tools = create_book_sql_tools(object())

        self.assertEqual(tools, expected_tools)
        url = create_engine.call_args.args[0]
        self.assertEqual(url.drivername, 'mysql+pymysql')
        self.assertEqual(url.username, 'reader')
        self.assertEqual(url.database, 'library')
        inspect.assert_called_once_with(engine)
        sql_database.assert_called_once()
        self.assertEqual(sql_database.call_args.kwargs['include_tables'], ['books'])
        self.assertEqual(sql_database.call_args.kwargs['sample_rows_in_table_info'], 0)
        self.assertTrue(sql_database.call_args.kwargs['lazy_table_reflection'])


if __name__ == '__main__':
    unittest.main()
