"""
database/database.py
---------------------
Handles persistence of weather search history using SQLite.

Ported from the original Tkinter application's `database.py`. The
same `search_history` table and pruning behaviour (keep only the most
recent `MAX_HISTORY_RECORDS` rows) are preserved so an existing
`weather_history.db` file from the desktop app can be reused as-is.
All database access is centralized here so route handlers never write
raw SQL.
"""
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import List, Optional

from backend.config import DATABASE_NAME, MAX_HISTORY_RECORDS


class DatabaseError(Exception):
    """Raised when a database operation fails."""


class WeatherDatabase:
    """Manages the SQLite-backed search history for the weather application."""

    def __init__(self, db_name: str = DATABASE_NAME):
        self.db_name = db_name
        self._create_table()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_name)
        try:
            yield conn
            conn.commit()
        except sqlite3.Error as exc:
            conn.rollback()
            raise DatabaseError(f"Database operation failed: {exc}") from exc
        finally:
            conn.close()

    def _create_table(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS search_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    city TEXT NOT NULL,
                    country TEXT,
                    temperature REAL,
                    description TEXT,
                    searched_at TEXT NOT NULL
                )
                """
            )

    def add_search(self, city: str, country: Optional[str], temperature, description: Optional[str]) -> int:
        """Insert a new search record, prune old rows, and return the new row's id."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO search_history (city, country, temperature, description, searched_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (city, country, temperature, description, timestamp),
            )
            new_id = cursor.lastrowid
            cursor.execute(
                """
                DELETE FROM search_history
                WHERE id NOT IN (
                    SELECT id FROM search_history
                    ORDER BY id DESC
                    LIMIT ?
                )
                """,
                (MAX_HISTORY_RECORDS,),
            )
            return new_id

    def get_history(self, limit: int = MAX_HISTORY_RECORDS) -> List[dict]:
        """Return the most recent search records, newest first, as dicts."""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, city, country, temperature, description, searched_at
                FROM search_history
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def delete_entry(self, record_id: int) -> bool:
        """Delete a single history record by id. Returns True if a row was removed."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM search_history WHERE id = ?", (record_id,))
            return cursor.rowcount > 0

    def clear_history(self) -> None:
        """Delete all stored search history records."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM search_history")


# A single shared instance used across the app (FastAPI dependency).
db = WeatherDatabase()
