from __future__ import annotations

import logging
import sqlite3

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 4


def initialize_schema(conn: sqlite3.Connection) -> None:
    create_tables(conn)
    apply_migrations(conn)


def create_tables(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.commit()


def apply_migrations(conn: sqlite3.Connection) -> None:
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version < 1:
        _migrate_v0_to_v1(conn)
    if version < 2:
        _migrate_v1_to_v2(conn)
    if version < 3:
        _migrate_v2_to_v3(conn)
    if version < 4:
        _migrate_v3_to_v4(conn)
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    if current < SCHEMA_VERSION:
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.commit()


def _migrate_v0_to_v1(conn: sqlite3.Connection) -> None:
    logger.info("Schema migration: v0 -> v1 (initial tables)")
    conn.execute("PRAGMA user_version = 1")
    conn.commit()


def _migrate_v1_to_v2(conn: sqlite3.Connection) -> None:
    logger.info("Schema migration: v1 -> v2 (multi-config support)")
    conn.execute("PRAGMA user_version = 2")
    conn.commit()


def _migrate_v2_to_v3(conn: sqlite3.Connection) -> None:
    # Historically added LLM-scan-config validation columns. The LLM scan feature
    # has since been removed and its table is dropped in v3 -> v4, so this is a
    # no-op version bump kept only to preserve the migration sequence.
    logger.info("Schema migration: v2 -> v3 (no-op; LLM scan config removed)")
    conn.execute("PRAGMA user_version = 3")
    conn.commit()


def _migrate_v3_to_v4(conn: sqlite3.Connection) -> None:
    logger.info("Schema migration: v3 -> v4 (drop removed LLM scan config table)")
    conn.execute("DROP TABLE IF EXISTS llm_scan_configs")
    conn.execute("PRAGMA user_version = 4")
    conn.commit()
