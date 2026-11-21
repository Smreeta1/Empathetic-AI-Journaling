import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "memory.db"


def get_connection():
    """Create a connection to the local SQLite database with foreign keys and busy timeout."""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH, timeout=30)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")
    return connection


def migrate_database():
    """
    Safely migrate schema v1 -> v2 while preserving all existing rows.
    Never deletes or resets data/memory.db.
    """
    if not DATABASE_PATH.exists():
        return

    connection = sqlite3.connect(DATABASE_PATH, timeout=30)
    try:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version in (0, 2):
            return
        if version != 1:
            raise RuntimeError(f"Unsupported database version: {version}")

        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute("BEGIN IMMEDIATE")

        connection.execute("""
            CREATE TABLE memory_nodes_new (
                id TEXT PRIMARY KEY,
                node_type TEXT NOT NULL
                    CHECK (
                        node_type IN (
                            'person',
                            'event',
                            'state',
                            'topic',
                            'assertion',
                            'preference'
                        )
                    ),
                content TEXT NOT NULL,
                source_entry_id TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                valid_from TEXT,
                valid_until TEXT,
                sensitivity_level TEXT NOT NULL DEFAULT 'normal'
                    CHECK (
                        sensitivity_level IN (
                            'normal',
                            'sensitive',
                            'highly_sensitive'
                        )
                    ),
                confidence REAL
                    CHECK (
                        confidence IS NULL
                        OR (confidence >= 0 AND confidence <= 1)
                    ),
                approval_status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (
                        approval_status IN (
                            'pending',
                            'approved',
                            'rejected'
                        )
                    )
            )
        """)

        connection.execute("""
            INSERT INTO memory_nodes_new (
                id,
                node_type,
                content,
                source_entry_id,
                created_at,
                updated_at,
                valid_from,
                valid_until,
                sensitivity_level,
                confidence,
                approval_status
            )
            SELECT
                id,
                node_type,
                content,
                source_entry_id,
                created_at,
                created_at,
                valid_from,
                valid_until,
                sensitivity_level,
                confidence,
                approval_status
            FROM memory_nodes
        """)

        connection.execute("""
            CREATE TABLE memory_edges_new (
                id TEXT PRIMARY KEY,
                source_node_id TEXT NOT NULL,
                target_node_id TEXT NOT NULL,
                relationship_type TEXT NOT NULL
                    CHECK (
                        relationship_type IN (
                            'related_to',
                            'involved_in',
                            'happened_before',
                            'changed_to',
                            'supports',
                            'contradicts'
                        )
                    ),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                evidence TEXT,
                FOREIGN KEY (source_node_id)
                    REFERENCES memory_nodes_new(id)
                    ON DELETE CASCADE,
                FOREIGN KEY (target_node_id)
                    REFERENCES memory_nodes_new(id)
                    ON DELETE CASCADE,
                CHECK (source_node_id != target_node_id)
            )
        """)

        connection.execute("""
            INSERT INTO memory_edges_new
            SELECT * FROM memory_edges
        """)

        connection.execute("DROP TABLE memory_edges")
        connection.execute("DROP TABLE memory_nodes")
        connection.execute("ALTER TABLE memory_nodes_new RENAME TO memory_nodes")
        connection.execute("ALTER TABLE memory_edges_new RENAME TO memory_edges")

        connection.execute("CREATE INDEX idx_nodes_type ON memory_nodes(node_type)")
        connection.execute("CREATE INDEX idx_nodes_approval ON memory_nodes(approval_status)")
        connection.execute("CREATE INDEX idx_edges_source ON memory_edges(source_node_id)")
        connection.execute("CREATE INDEX idx_edges_target ON memory_edges(target_node_id)")
        connection.execute("PRAGMA user_version = 2")
        connection.commit()

        connection.execute("PRAGMA foreign_keys = ON")
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError(f"Foreign-key violations detected: {violations}")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database():
    """Create tables if missing without touching or resetting existing data."""
    migrate_database()
    with get_connection() as connection:
        connection.execute("PRAGMA journal_mode = WAL")

        connection.execute("""
            CREATE TABLE IF NOT EXISTS journal_entries (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                mood_hint TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS memory_nodes (
                id TEXT PRIMARY KEY,
                node_type TEXT NOT NULL
                    CHECK (
                        node_type IN (
                            'person',
                            'event',
                            'state',
                            'topic',
                            'assertion',
                            'preference'
                        )
                    ),
                content TEXT NOT NULL,
                source_entry_id TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                valid_from TEXT,
                valid_until TEXT,
                sensitivity_level TEXT NOT NULL DEFAULT 'normal'
                    CHECK (
                        sensitivity_level IN (
                            'normal',
                            'sensitive',
                            'highly_sensitive'
                        )
                    ),
                confidence REAL
                    CHECK (
                        confidence IS NULL
                        OR (confidence >= 0 AND confidence <= 1)
                    ),
                approval_status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (
                        approval_status IN (
                            'pending',
                            'approved',
                            'rejected'
                        )
                    )
            )
        """)

        cols = {
            row[1]
            for row in connection.execute("PRAGMA table_info(memory_nodes)").fetchall()
        }
        if "updated_at" not in cols:
            connection.execute("ALTER TABLE memory_nodes ADD COLUMN updated_at TEXT")
            connection.execute("UPDATE memory_nodes SET updated_at = created_at WHERE updated_at IS NULL")

        connection.execute("""
            CREATE TABLE IF NOT EXISTS memory_edges (
                id TEXT PRIMARY KEY,
                source_node_id TEXT NOT NULL,
                target_node_id TEXT NOT NULL,
                relationship_type TEXT NOT NULL
                    CHECK (
                        relationship_type IN (
                            'related_to',
                            'involved_in',
                            'happened_before',
                            'changed_to',
                            'supports',
                            'contradicts'
                        )
                    ),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                evidence TEXT,
                FOREIGN KEY (source_node_id)
                    REFERENCES memory_nodes(id)
                    ON DELETE CASCADE,
                FOREIGN KEY (target_node_id)
                    REFERENCES memory_nodes(id)
                    ON DELETE CASCADE,
                CHECK (source_node_id != target_node_id)
            )
        """)

        connection.execute("CREATE INDEX IF NOT EXISTS idx_nodes_type ON memory_nodes(node_type)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_nodes_approval ON memory_nodes(approval_status)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_edges_source ON memory_edges(source_node_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_edges_target ON memory_edges(target_node_id)")
        connection.execute("PRAGMA user_version = 2")


if __name__ == "__main__":
    initialize_database()
    print(f"Database ready at: {DATABASE_PATH}")