
import sqlite3
import uuid

from memory.schema import get_connection


def add_node(
    node_type,
    content,
    source_entry_id=None,
    valid_from=None,
    valid_until=None,
    sensitivity_level="normal",
    confidence=None,
):
    """
    Add a new memory node to the database.

    New nodes are pending until explicitly approved.
    """

    node_id = str(uuid.uuid4())

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO memory_nodes (
                id,
                node_type,
                content,
                source_entry_id,
                valid_from,
                valid_until,
                sensitivity_level,
                confidence
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                node_id,
                node_type,
                content,
                source_entry_id,
                valid_from,
                valid_until,
                sensitivity_level,
                confidence,
            ),
        )

    return node_id


def get_node(node_id):
    """Retrieve one memory node by its ID."""

    with get_connection() as connection:
        connection.row_factory = sqlite3.Row

        row = connection.execute(
            """
            SELECT *
            FROM memory_nodes
            WHERE id = ?
            """,
            (node_id,),
        ).fetchone()

    return dict(row) if row else None


def approve_node(node_id):
    """Approve a pending memory node."""

    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE memory_nodes
            SET approval_status = 'approved'
            WHERE id = ?
            AND approval_status = 'pending'
            """,
            (node_id,),
        )

    return cursor.rowcount == 1


def reject_node(node_id):
    """Reject a pending memory node."""

    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE memory_nodes
            SET approval_status = 'rejected'
            WHERE id = ?
            AND approval_status = 'pending'
            """,
            (node_id,),
        )

    return cursor.rowcount == 1


def add_edge(
    source_node_id,
    target_node_id,
    relationship_type,
    evidence=None,
):
    """Create a relationship between two existing memory nodes."""

    edge_id = str(uuid.uuid4())

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO memory_edges (
                id,
                source_node_id,
                target_node_id,
                relationship_type,
                evidence
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                edge_id,
                source_node_id,
                target_node_id,
                relationship_type,
                evidence,
            ),
        )

    return edge_id


def get_connected_nodes(node_id):
    """
    Retrieve nodes directly connected to the given node.

    Connections are returned in both directions.
    """

    with get_connection() as connection:
        connection.row_factory = sqlite3.Row

        rows = connection.execute(
            """
            SELECT
                n.*,
                e.id AS edge_id,
                e.relationship_type,
                'outgoing' AS direction
            FROM memory_edges e
            JOIN memory_nodes n
                ON n.id = e.target_node_id
            WHERE e.source_node_id = ?

            UNION ALL

            SELECT
                n.*,
                e.id AS edge_id,
                e.relationship_type,
                'incoming' AS direction
            FROM memory_edges e
            JOIN memory_nodes n
                ON n.id = e.source_node_id
            WHERE e.target_node_id = ?
            """,
            (node_id, node_id),
        ).fetchall()

    return [dict(row) for row in rows]


def delete_node(node_id):
    """
    Delete a memory node.

    SQLite automatically deletes its connected edges
    because the schema uses ON DELETE CASCADE.
    """

    with get_connection() as connection:
        cursor = connection.execute(
            """
            DELETE FROM memory_nodes
            WHERE id = ?
            """,
            (node_id,),
        )

    return cursor.rowcount == 1
