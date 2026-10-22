from pathlib import Path
import unittest


class LibraryMigrationTests(unittest.TestCase):
    def test_borrow_schema_migration_is_additive_and_matches_business_queries(self):
        migration = (
            Path(__file__).resolve().parents[1]
            / "database"
            / "migrations"
            / "001_create_member_borrow_tables.sql"
        )
        sql = migration.read_text(encoding="utf-8").upper()

        self.assertIn("CREATE TABLE IF NOT EXISTS MEMBERS", sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS BORROW_RECORDS", sql)
        self.assertIn("MEMBER_ID", sql)
        self.assertIn("BOOK_ID", sql)
        self.assertIn("BORROWED_AT", sql)
        self.assertIn("DUE_AT", sql)
        self.assertIn("RETURNED_AT", sql)
        self.assertIn("STATUS", sql)
        self.assertIn("REFERENCES BOOKS (ID)", sql)
        self.assertNotIn("DROP TABLE", sql)
        self.assertNotIn("ALTER TABLE BOOKS", sql)
        self.assertNotIn("DELETE FROM", sql)


if __name__ == "__main__":
    unittest.main()
