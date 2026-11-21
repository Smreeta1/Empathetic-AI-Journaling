import sqlite3
import uuid

from memory.schema import get_connection


def save_journal_entry(content, mood_hint=None):
    entry_id = str(uuid.uuid4())
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO journal_entries (id, content, mood_hint)
            VALUES (?, ?, ?)
            """,
            (entry_id, content.strip(), mood_hint),
        )
    return entry_id


def get_all_nodes():
    with get_connection() as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT * FROM memory_nodes ORDER BY created_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def get_all_edges():
    with get_connection() as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT * FROM memory_edges ORDER BY created_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def get_approved_nodes():
    with get_connection() as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT * FROM memory_nodes
            WHERE approval_status = 'approved'
            ORDER BY created_at DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def add_node(
    node_type,
    content,
    source_entry_id=None,
    valid_from=None,
    valid_until=None,
    sensitivity_level="normal",
    confidence=None,
    auto_approve=False,
):
    cleaned_content = " ".join(content.strip().split())
    normalized_content = cleaned_content.casefold()
    initial_status = "approved" if auto_approve else "pending"

    with get_connection() as connection:
        connection.row_factory = sqlite3.Row
        existing_nodes = connection.execute(
            """
            SELECT id, node_type, content, approval_status
            FROM memory_nodes
            WHERE approval_status IN ('pending', 'approved')
            AND node_type = ?
            """,
            (node_type,),
        ).fetchall()

        for existing in existing_nodes:
            existing_content = " ".join(existing["content"].casefold().split())
            if existing_content == normalized_content:
                if auto_approve and existing["approval_status"] != "approved":
                    connection.execute(
                        """
                        UPDATE memory_nodes
                        SET approval_status = 'approved',
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (existing["id"],),
                    )
                return existing["id"]

        node_id = str(uuid.uuid4())
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
                confidence,
                approval_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                node_id,
                node_type,
                cleaned_content,
                source_entry_id,
                valid_from,
                valid_until,
                sensitivity_level,
                confidence,
                initial_status,
            ),
        )

    return node_id


def get_node(node_id):
    with get_connection() as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT * FROM memory_nodes WHERE id = ?",
            (node_id,),
        ).fetchone()
    return dict(row) if row else None


def approve_node(node_id):
    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE memory_nodes
            SET approval_status = 'approved',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (node_id,),
        )
    return cursor.rowcount == 1


def approve_all_pending_nodes():
    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE memory_nodes
            SET approval_status = 'approved',
                updated_at = CURRENT_TIMESTAMP
            WHERE approval_status = 'pending'
            """
        )
    return cursor.rowcount


def reject_node(node_id):
    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE memory_nodes
            SET approval_status = 'rejected',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
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
    with get_connection() as connection:
        existing = connection.execute(
            """
            SELECT id, evidence
            FROM memory_edges
            WHERE source_node_id = ?
            AND target_node_id = ?
            AND relationship_type = ?
            """,
            (source_node_id, target_node_id, relationship_type),
        ).fetchone()

        if existing:
            if evidence and not existing[1]:
                connection.execute(
                    "UPDATE memory_edges SET evidence = ? WHERE id = ?",
                    (evidence, existing[0]),
                )
            return existing[0]

        edge_id = str(uuid.uuid4())
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

        if relationship_type == "changed_to":
            connection.execute(
                """
                UPDATE memory_nodes
                SET valid_until = COALESCE(valid_until, CURRENT_TIMESTAMP),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (source_node_id,),
            )

    return edge_id


def get_connected_nodes(node_id):
    with get_connection() as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT
                n.*,
                e.id AS edge_id,
                e.relationship_type,
                e.evidence,
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
                e.evidence,
                'incoming' AS direction
            FROM memory_edges e
            JOIN memory_nodes n
                ON n.id = e.source_node_id
            WHERE e.target_node_id = ?
            """,
            (node_id, node_id),
        ).fetchall()
    return [dict(row) for row in rows]


def get_approved_connected_nodes(node_id):
    return [
        node
        for node in get_connected_nodes(node_id)
        if node.get("approval_status") == "approved"
    ]


def expand_approved_subgraph(seed_node_ids):
    """Expand 1 hop across approved nodes and edges, preserving evidence."""
    visited_nodes = {}
    collected_edges = {}

    for nid in seed_node_ids:
        seed = get_node(nid)
        if seed and seed.get("approval_status") == "approved":
            visited_nodes[nid] = seed

    for nid in list(visited_nodes.keys()):
        for neighbor in get_approved_connected_nodes(nid):
            neighbor_id = neighbor["id"]
            edge_id = neighbor["edge_id"]

            if neighbor_id not in visited_nodes:
                visited_nodes[neighbor_id] = {
                    k: v
                    for k, v in neighbor.items()
                    if k not in ("edge_id", "relationship_type", "evidence", "direction")
                }

            if edge_id not in collected_edges:
                if neighbor["direction"] == "outgoing":
                    src_id, tgt_id = nid, neighbor_id
                else:
                    src_id, tgt_id = neighbor_id, nid

                collected_edges[edge_id] = {
                    "id": edge_id,
                    "source_node_id": src_id,
                    "target_node_id": tgt_id,
                    "relationship_type": neighbor["relationship_type"],
                    "evidence": neighbor.get("evidence"),
                }

    return {
        "nodes": list(visited_nodes.values()),
        "edges": list(collected_edges.values()),
    }


def delete_node(node_id):
    with get_connection() as connection:
        cursor = connection.execute(
            "DELETE FROM memory_nodes WHERE id = ?",
            (node_id,),
        )
    return cursor.rowcount == 1


def delete_all_graph_data():
    """Explicitly clear all memory nodes and edges when confirmed in the UI."""
    with get_connection() as connection:
        connection.execute("DELETE FROM memory_edges")
        connection.execute("DELETE FROM memory_nodes")