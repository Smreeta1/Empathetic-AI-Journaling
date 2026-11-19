
ALLOWED_NODE_TYPES = {
    "person",
    "event",
    "state",
    "topic",
    "assertion",
    "preference",
}
ALLOWED_SENSITIVITY_LEVELS = {
    "normal",
    "sensitive",
    "highly_sensitive",
}

ALLOWED_RELATIONSHIP_TYPES = {
    "related_to",
    "involved_in",
    "happened_before",
    "changed_to",
    "supports",
    "contradicts",
}


def validate_memory_candidate(candidate):
    """
    Validate one proposed memory before database storage.

    Returns:
        (True, None) when valid.
        (False, error_message) when invalid.
    """

    if not isinstance(candidate, dict):
        return False, "Memory candidate must be a dictionary."

    required_fields = {
        "node_type",
        "content",
        "sensitivity_level",
        "confidence",
    }

    missing_fields = required_fields - candidate.keys()

    if missing_fields:
        return False, f"Missing fields: {sorted(missing_fields)}"

    if candidate["node_type"] not in ALLOWED_NODE_TYPES:
        return False, "Invalid node type."

    if not isinstance(candidate["content"], str):
        return False, "Content must be a string."

    if not candidate["content"].strip():
        return False, "Content cannot be empty."

    if candidate["sensitivity_level"] not in ALLOWED_SENSITIVITY_LEVELS:
        return False, "Invalid sensitivity level."

    confidence = candidate["confidence"]

    # bool is a subclass of int in Python, so reject it explicitly.
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        return False, "Confidence must be a number."

    if not 0 <= confidence <= 1:
        return False, "Confidence must be between 0 and 1."

    return True, None


def validate_relationship_candidate(candidate):
    """
    Validate a proposed relationship between two memory nodes.
    """

    if not isinstance(candidate, dict):
        return False, "Relationship candidate must be a dictionary."

    required_fields = {
        "source_node_id",
        "target_node_id",
        "relationship_type",
    }

    missing_fields = required_fields - candidate.keys()

    if missing_fields:
        return False, f"Missing fields: {sorted(missing_fields)}"

    if not isinstance(candidate["source_node_id"], str):
        return False, "Source node ID must be a string."

    if not isinstance(candidate["target_node_id"], str):
        return False, "Target node ID must be a string."

    if not candidate["source_node_id"].strip():
        return False, "Source node ID cannot be empty."

    if not candidate["target_node_id"].strip():
        return False, "Target node ID cannot be empty."

    if candidate["source_node_id"] == candidate["target_node_id"]:
        return False, "A node cannot connect to itself."

    if candidate["relationship_type"] not in ALLOWED_RELATIONSHIP_TYPES:
        return False, "Invalid relationship type."

    return True, None
