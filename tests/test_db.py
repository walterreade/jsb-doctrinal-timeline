"""Tests for database utilities."""

import pytest

from pipeline.utils.db import Database


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.db"


@pytest.fixture
def schema_path(tmp_path):
    schema = tmp_path / "schema.sql"
    schema.write_text("""
        CREATE TABLE IF NOT EXISTS documents (
            sha256 TEXT PRIMARY KEY,
            title TEXT,
            source_type TEXT,
            provenance_class TEXT,
            recorder TEXT,
            event_date_edtf TEXT,
            event_date_earliest TEXT,
            event_date_latest TEXT,
            record_date_edtf TEXT,
            record_date_earliest TEXT,
            record_date_latest TEXT,
            repository TEXT,
            citation TEXT,
            normalized_text TEXT,
            normalized_text_sha256 TEXT
        );
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_sha256 TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            char_start INTEGER NOT NULL,
            char_end INTEGER NOT NULL,
            chunk_text TEXT NOT NULL,
            FOREIGN KEY (document_sha256) REFERENCES documents(sha256)
        );
        CREATE TABLE IF NOT EXISTS assertions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_sha256 TEXT NOT NULL,
            chunk_id INTEGER NOT NULL,
            principle_statement TEXT NOT NULL,
            verbatim_quote TEXT NOT NULL,
            char_start INTEGER NOT NULL,
            char_end INTEGER NOT NULL,
            explicit_or_inferred TEXT,
            verification TEXT NOT NULL,
            fuzzy_score REAL,
            confidence REAL,
            audience TEXT,
            event_date_edtf TEXT,
            reasoning TEXT,
            FOREIGN KEY (document_sha256) REFERENCES documents(sha256),
            FOREIGN KEY (chunk_id) REFERENCES chunks(id)
        );
        CREATE TABLE IF NOT EXISTS quarantine (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_sha256 TEXT NOT NULL,
            chunk_id INTEGER NOT NULL,
            raw_json TEXT,
            principle_statement TEXT,
            attempted_quote TEXT,
            reason TEXT NOT NULL,
            FOREIGN KEY (document_sha256) REFERENCES documents(sha256),
            FOREIGN KEY (chunk_id) REFERENCES chunks(id)
        );
    """, encoding="utf-8")
    return schema


class TestDatabaseContextManager:
    def test_enter_exit(self, db_path):
        with Database(db_path) as db:
            assert db.conn is not None
        assert db.conn is None

    def test_creates_parent_dir(self, tmp_path):
        db_path = tmp_path / "nested" / "dir" / "test.db"
        with Database(db_path) as db:
            db.execute("SELECT 1")
        assert db_path.exists()

    def test_commits_on_success(self, db_path):
        with Database(db_path) as db:
            db.execute("CREATE TABLE t (x INTEGER)")
            db.execute("INSERT INTO t VALUES (42)")
        with Database(db_path) as db:
            row = db.execute("SELECT x FROM t").fetchone()
            assert row["x"] == 42

    def test_rollback_on_exception(self, db_path):
        with Database(db_path) as db:
            db.execute("CREATE TABLE t (x INTEGER)")
        try:
            with Database(db_path) as db:
                db.execute("INSERT INTO t VALUES (42)")
                raise ValueError("force rollback")
        except ValueError:
            pass
        with Database(db_path) as db:
            row = db.execute("SELECT COUNT(*) as count FROM t").fetchone()
            assert row["count"] == 0

    def test_foreign_keys_enabled(self, db_path, schema_path):
        with Database(db_path) as db:
            db.initialize_schema(schema_path)
            row = db.execute("PRAGMA foreign_keys").fetchone()
            assert row[0] == 1

    def test_wal_mode_enabled(self, db_path):
        with Database(db_path) as db:
            row = db.execute("PRAGMA journal_mode").fetchone()
            assert row[0] == "wal"


class TestDatabaseOperations:
    def test_execute_without_connection_raises(self, db_path):
        db = Database(db_path)
        with pytest.raises(RuntimeError, match="not connected"):
            db.execute("SELECT 1")

    def test_initialize_schema(self, db_path, schema_path):
        with Database(db_path) as db:
            db.initialize_schema(schema_path)
            tables = db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            table_names = [t["name"] for t in tables]
            assert "documents" in table_names
            assert "chunks" in table_names
            assert "assertions" in table_names
            assert "quarantine" in table_names


class TestSafeDivide:
    def test_normal_division(self, db_path):
        with Database(db_path) as db:
            assert db._safe_divide(10, 5) == 2.0

    def test_zero_denominator(self, db_path):
        with Database(db_path) as db:
            assert db._safe_divide(10, 0) == 0.0

    def test_zero_numerator(self, db_path):
        with Database(db_path) as db:
            assert db._safe_divide(0, 5) == 0.0


class TestGetStats:
    def test_empty_database(self, db_path, schema_path):
        with Database(db_path) as db:
            db.initialize_schema(schema_path)
            stats = db.get_stats()
            assert stats["documents"] == 0
            assert stats["chunks"] == 0
            assert stats["assertions_total"] == 0
            assert stats["quarantined"] == 0
            assert stats["verification_rate"] == 0.0
            assert stats["quarantine_rate"] == 0.0
