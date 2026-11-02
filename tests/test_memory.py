import os
import unittest
from unittest.mock import patch, MagicMock

from config import get_memory_user_id
from database.init_db import initialize_database
from tools.memory_tools import read_memory, save_memory


class MemoryTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {"LIBRARY_USER_ID": "test-user"}, clear=False)
        environment.start()
        self.addCleanup(environment.stop)

    def test_get_memory_user_id_from_env(self):
        """Test that get_memory_user_id reads from LIBRARY_USER_ID environment variable"""
        with patch.dict(os.environ, {"LIBRARY_USER_ID": "test-user-123"}, clear=False):
            self.assertEqual(get_memory_user_id(), "test-user-123")

    def test_get_memory_user_id_fails_closed_when_unset(self):
        """Memory operations must not fall back to a shared user identity."""
        env_without_user_id = {k: v for k, v in os.environ.items() if k != "LIBRARY_USER_ID"}
        with patch.dict(os.environ, env_without_user_id, clear=True):
            with self.assertRaises(RuntimeError):
                get_memory_user_id()

    @patch("database.init_db.get_connection")
    def test_initialize_database_creates_user_memories_table(self, mock_get_connection):
        """Test that initialize_database creates the user_memories table with correct schema"""
        # Setup mock connection and cursor
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_get_connection.return_value = mock_connection
        mock_connection.cursor.return_value = mock_cursor

        # Call the function
        initialize_database()

        # Verify that get_connection was called
        mock_get_connection.assert_called_once()

        # Verify that cursor was called
        mock_connection.cursor.assert_called_once()

        # Verify that execute was called twice (for books and user_memories tables)
        self.assertEqual(mock_cursor.execute.call_count, 2)

        # Get all the SQL calls made to execute
        execute_calls = [call[0][0] for call in mock_cursor.execute.call_args_list]

        # Check that one of the calls was for creating the user_memories table
        user_memories_table_sql = None
        for sql in execute_calls:
            if "CREATE TABLE IF NOT EXISTS user_memories" in sql:
                user_memories_table_sql = sql
                break

        self.assertIsNotNone(user_memories_table_sql, "user_memories table creation SQL not found in execute calls")

        # Check that the SQL contains the expected table creation
        self.assertIn("id INT AUTO_INCREMENT PRIMARY KEY", user_memories_table_sql)
        self.assertIn("user_id VARCHAR(255) NOT NULL", user_memories_table_sql)
        self.assertIn("memory_key VARCHAR(255) NOT NULL", user_memories_table_sql)
        self.assertIn("memory_value TEXT", user_memories_table_sql)
        self.assertIn("created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP", user_memories_table_sql)
        self.assertIn("updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP", user_memories_table_sql)
        self.assertIn("UNIQUE KEY unique_user_memory (user_id, memory_key)", user_memories_table_sql)

        # Verify that commit was called
        mock_connection.commit.assert_called_once()

        # Verify that cursor and connection were closed
        mock_cursor.close.assert_called_once()
        mock_connection.close.assert_called_once()

    @patch("tools.memory_tools.get_connection")
    def test_save_memory_upsert_and_commit(self, mock_get_connection):
        """Test that save_memory inserts a new memory and updates on duplicate key"""
        # Setup mock connection and cursor
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_get_connection.return_value = mock_connection
        mock_connection.cursor.return_value = mock_cursor

        # Call save_memory
        result = save_memory.invoke({"memory_key": "test_key", "memory_value": "test_value"})

        # Verify that get_connection was called
        mock_get_connection.assert_called_once()

        # Verify that cursor was called with dictionary=True
        mock_connection.cursor.assert_called_once_with(dictionary=True)

        # Verify that execute was called (once for the upsert)
        mock_cursor.execute.assert_called_once()
        # Get the SQL and parameters used
        sql, params = mock_cursor.execute.call_args[0]
        # Check that the SQL is the upsert query
        self.assertIn("INSERT INTO user_memories", sql)
        self.assertIn("ON DUPLICATE KEY UPDATE", sql)
        # Check that the parameters are correct (user_id, memory_key, memory_value)
        self.assertEqual(params, ("test-user", "test_key", "test_value"))

        # Verify that commit was called
        mock_connection.commit.assert_called_once()

        # Verify that cursor and connection were closed
        mock_cursor.close.assert_called_once()
        mock_connection.close.assert_called_once()

        # Check the result string
        self.assertIn("Memory saved with key 'test_key'", result)

    @patch("tools.memory_tools.get_connection")
    def test_read_memory_matching(self, mock_get_connection):
        """Test that read_memory returns matching memories based on query"""
        # Setup mock connection and cursor
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_get_connection.return_value = mock_connection
        mock_connection.cursor.return_value = mock_cursor

        # Mock the fetchall to return some rows
        mock_cursor.fetchall.return_value = [
            {"memory_key": "key1", "memory_value": "This is a test value"},
            {"memory_key": "key2", "memory_value": "Another test value"},
        ]

        # Call read_memory with a query
        result = read_memory.invoke({"query": "test"})

        # Verify that get_connection was called
        mock_get_connection.assert_called_once()

        # Verify that cursor was called with dictionary=True
        mock_connection.cursor.assert_called_once_with(dictionary=True)

        # Verify that execute was called once
        mock_cursor.execute.assert_called_once()
        # Get the SQL and parameters used
        sql, params = mock_cursor.execute.call_args[0]
        # Check that the SQL contains the LIKE clause
        self.assertIn("LIKE %s", sql)
        self.assertIn("ORDER BY updated_at DESC", sql)
        self.assertIn("LIMIT 5", sql)
        # Check that the parameters include the user_id and the search term with wildcards
        self.assertEqual(params[0], "test-user")  # user_id
        self.assertEqual(params[1], "%test%")  # search term

        # Verify that cursor and connection were closed
        mock_cursor.close.assert_called_once()
        mock_connection.close.assert_called_once()

        # Check that the result contains the expected strings
        self.assertIn("Key: key1", result)
        self.assertIn("Value: This is a test value", result)
        self.assertIn("Key: key2", result)
        self.assertIn("Value: Another test value", result)

    @patch("tools.memory_tools.get_connection")
    def test_read_memory_no_match(self, mock_get_connection):
        """Test that read_memory returns a message when no memories match"""
        # Setup mock connection and cursor
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_get_connection.return_value = mock_connection
        mock_connection.cursor.return_value = mock_cursor

        # Mock the fetchall to return empty list
        mock_cursor.fetchall.return_value = []

        # Call read_memory with a query that doesn't match
        result = read_memory.invoke({"query": "nonexistent"})

        # Verify that get_connection was called
        mock_get_connection.assert_called_once()

        # Verify that cursor was called with dictionary=True
        mock_connection.cursor.assert_called_once_with(dictionary=True)

        # Verify that execute was called once
        mock_cursor.execute.assert_called_once()

        # Verify that cursor and connection were closed
        mock_cursor.close.assert_called_once()
        mock_connection.close.assert_called_once()

        # Check that the result is the no match message
        self.assertEqual(result, "No memories found matching 'nonexistent'.")


if __name__ == "__main__":
    unittest.main()