
import sqlite3
from pathlib import Path


# Project root directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Local database location
DATABASE_PATH = PROJECT_ROOT / "data" / "memory.db"


def get_connection():
    """
    Create a connection to the local SQLite database.
    """

    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH)

    # Enforce foreign-key relationships
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def migrate_database():
    """
    Migrate database schema from version 1 to version 2.

    Version 2 adds 'preference' as a supported memory node type.
    Existing nodes and relationships are preserved.
    """

    connection = sqlite3.connect(DATABASE_PATH)

    try:
        version = connection.execute(
            "PRAGMA user_version"
        ).fetchone()[0]

        if version == 2:
            print("Database is already at schema version 2.")
            return

        if version != 1:
            raise RuntimeError(
                f"Unsupported database version: {version}"
            )

        # Temporarily disable foreign-key enforcement so we can
        # rebuild the related tables safely.
        connection.execute("PRAGMA foreign_keys = OFF")

        connection.execute("BEGIN IMMEDIATE")

        # Create the replacement nodes table with 'preference'.
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

        # Copy all existing memory nodes.
        connection.execute("""
            INSERT INTO memory_nodes_new
            SELECT * FROM memory_nodes
        """)

        # Create replacement edges table.
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

        # Copy all existing relationships.
        connection.execute("""
            INSERT INTO memory_edges_new
            SELECT * FROM memory_edges
        """)

        # Remove old tables. Drop edges first because they reference nodes.
        connection.execute("DROP TABLE memory_edges")
        connection.execute("DROP TABLE memory_nodes")

        # Rename replacement tables to their original names.
        connection.execute("""
            ALTER TABLE memory_nodes_new
            RENAME TO memory_nodes
        """)

        connection.execute("""
            ALTER TABLE memory_edges_new
            RENAME TO memory_edges
        """)

        # Recreate indexes.
        connection.execute("""
            CREATE INDEX idx_nodes_type
            ON memory_nodes(node_type)
        """)

        connection.execute("""
            CREATE INDEX idx_nodes_approval
            ON memory_nodes(approval_status)
        """)

        connection.execute("""
            CREATE INDEX idx_edges_source
            ON memory_edges(source_node_id)
        """)

        connection.execute("""
            CREATE INDEX idx_edges_target
            ON memory_edges(target_node_id)
        """)

        # Mark the migration as complete.
        connection.execute("PRAGMA user_version = 2")

        connection.commit()

        # Check that the rebuilt foreign-key relationships are valid.
        connection.execute("PRAGMA foreign_keys = ON")

        violations = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        if violations:
            raise RuntimeError(
                f"Foreign-key violations detected: {violations}"
            )

        print("Database successfully migrated from version 1 to 2.")

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()



def initialize_database():
    """
    Create the memory graph tables if they do not exist.
    """
    migrate_database()
    with get_connection() as connection:

        # Table 1: Individual memory records
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

        # Table 2: Relationships between memory records
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

        # Indexes for common lookup operations
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_nodes_type
            ON memory_nodes(node_type)
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_nodes_approval
            ON memory_nodes(approval_status)
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_edges_source
            ON memory_edges(source_node_id)
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_edges_target
            ON memory_edges(target_node_id)
        """)

        # Record the current database schema version
        connection.execute("PRAGMA user_version = 2")


if __name__ == "__main__":
    initialize_database()
    print("Memory database initialized successfully.")
    print(f"Database location: {DATABASE_PATH}")
