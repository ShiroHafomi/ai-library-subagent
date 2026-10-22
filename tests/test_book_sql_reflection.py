import unittest
from unittest.mock import patch

from langchain_community.utilities import SQLDatabase
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool

from tools.book_tools import create_book_sql_tools


class BookSQLReflectionTests(unittest.TestCase):
    def test_book_schema_does_not_resolve_foreign_key_target_or_sample_rows(self):
        engine = create_engine("sqlite://", poolclass=StaticPool)
        self.addCleanup(engine.dispose)
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE users (id INTEGER PRIMARY KEY)")
            connection.exec_driver_sql(
                "CREATE TABLE books (id INTEGER PRIMARY KEY, "
                "user_id INTEGER REFERENCES users(id), title TEXT)"
            )
            connection.exec_driver_sql("INSERT INTO books (id, title) VALUES (1, 'Hidden title')")

        statements = []
        event.listen(
            engine,
            "before_cursor_execute",
            lambda _conn, _cursor, statement, _params, _context, _many: statements.append(statement),
        )

        with (
            patch("tools.book_tools.create_engine", return_value=engine),
            patch("tools.book_tools.SQLDatabase", wraps=SQLDatabase) as sql_database,
            patch("tools.book_tools.SQLDatabaseToolkit") as toolkit,
            patch.dict(
                "os.environ",
                {
                    "DB_READONLY_USER": "reader",
                    "DB_READONLY_PASSWORD": "reader-password",
                    "DB_HOST": "localhost",
                    "DB_PORT": "3306",
                    "DB_NAME": "library",
                },
                clear=True,
            ),
        ):
            toolkit.return_value.get_tools.return_value = []
            create_book_sql_tools(object())
            db = toolkit.call_args.kwargs["db"]
            table_info = db.get_table_info(["books"])

        sql_database.assert_called_once()
        self.assertTrue(sql_database.call_args.kwargs["lazy_table_reflection"])
        self.assertEqual(sql_database.call_args.kwargs["sample_rows_in_table_info"], 0)
        self.assertIn("CREATE TABLE books", table_info)
        self.assertNotIn("FOREIGN KEY", table_info)
        self.assertNotIn("Hidden title", table_info)
        self.assertFalse(any("users" in statement.lower() for statement in statements))
        self.assertFalse(any("select books" in statement.lower() for statement in statements))


if __name__ == "__main__":
    unittest.main()
