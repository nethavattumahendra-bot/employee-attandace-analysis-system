"""
Integration Tests for Live MySQL Server Connection and Schema Constraints.
Automatically skips if MySQL server is stopped or unreachable.
"""

import unittest
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from db import DatabaseManager


class TestMySQLIntegration(unittest.TestCase):
    """Integration test suite against live MySQL service."""

    @classmethod
    def setUpClass(cls):
        # Force MySQL engine preference
        os.environ["DB_ENGINE"] = "mysql"
        os.environ["ENABLE_DB_FALLBACK"] = "False"
        cls.db = DatabaseManager()

    def test_mysql_connection_and_table_schema(self):
        """Tests live MySQL connection if server is running, or provides clear guidance."""
        if not self.db.get_status()["is_mysql_active"]:
            self.skipTest(
                "MySQL Server is currently stopped/unreachable on localhost:3306. "
                "To run live MySQL tests: start MySQL service (`net start MySQL80` or `net start MySQL97`)."
            )

        # If connected, test table queries
        conn = self.db.get_connection()
        self.assertIsNotNone(conn)
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES;")
        tables = [t[0] for t in cursor.fetchall()]
        self.assertIn("employees", tables)
        self.assertIn("attendance", tables)
        cursor.close()
        conn.close()


if __name__ == "__main__":
    unittest.main()
