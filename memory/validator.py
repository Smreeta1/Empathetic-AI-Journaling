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


def sanitize_candidate(candidate):
    """
    Normalize common small-LLM formatting quirks so valid person/event/state
    nodes are preserved instead of silently discarded.
    """
    if not isinstance(candidate, dict):
        return candidate

    cleaned = dict(candidate)
    node_type = str(cleaned.get("node_type", "")).strip().lower()
    content = " ".join(str(cleaned.get("content", "")).strip().split())

    # Reclassify full-sentence feelings/statements if mislabeled as 'person'
    if node_type == "person" and (
        len(content.split()) > 6 or any(p in content for p in [".", "!", "?", "—"])
    ):
        lowered = content.lower()
        if any(
            w in lowered
            for w in ["feel", "felt", "scared", "afraid", "confused", "anxious", "happy", "sad", "holding"]
        ):
            node_type = "state"
        else:
            node_type = "assertion"

    # Default sensitivity_level if omitted or slightly misformatted by small model
    sens = str(cleaned.get("sensitivity_level", "normal")).strip().lower()
    if sens not in ALLOWED_SENSITIVITY_LEVELS:
        sens = "normal"

    # Coerce numeric string confidence or default to 0.85
    raw_conf = cleaned.get("confidence", 0.85)
    if isinstance(raw_conf, bool) or raw_conf is None:
        conf = 0.85
    else:
        try:
            conf = float(raw_conf)
            conf = max(0.0, min(1.0, conf))
        except (TypeError, ValueError):
            conf = 0.85

    cleaned["node_type"] = node_type
    cleaned["content"] = content
    cleaned["sensitivity_level"] = sens
    cleaned["confidence"] = conf
    return cleaned


def validate_memory_candidate(candidate):
    if not isinstance(candidate, dict):
        return False, "Memory candidate must be a dictionary."

    required_fields = {"node_type", "content", "sensitivity_level", "confidence"}
    missing = required_fields - candidate.keys()
    if missing:
        return False, f"Missing fields: {sorted(missing)}"

    if not isinstance(candidate["node_type"], str) or candidate["node_type"] not in ALLOWED_NODE_TYPES:
        return False, f"Invalid node type: {candidate.get('node_type')}"

    if not isinstance(candidate["content"], str) or len(" ".join(candidate["content"].strip().split())) < 2:
        return False, "Content must be a meaningful non-empty string."

    if (
        not isinstance(candidate["sensitivity_level"], str)
        or candidate["sensitivity_level"] not in ALLOWED_SENSITIVITY_LEVELS
    ):
        return False, "Invalid sensitivity level."

    confidence = candidate["confidence"]
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        return False, "Confidence must be a number."
    if not 0 <= confidence <= 1:
        return False, "Confidence must be between 0 and 1."

    return True, None


def validate_extracted_relationship(candidate, valid_temp_ids):
    if not isinstance(candidate, dict):
        return False, "Relationship candidate must be a dictionary."

    required_fields = {"source_temp_id", "target_temp_id", "relationship_type"}
    missing = required_fields - candidate.keys()
    if missing:
        return False, f"Missing fields: {sorted(missing)}"

    src = candidate["source_temp_id"]
    tgt = candidate["target_temp_id"]
    rel = candidate["relationship_type"]

    if not isinstance(src, str) or src not in valid_temp_ids:
        return False, f"Unknown source_temp_id: {src}"
    if not isinstance(tgt, str) or tgt not in valid_temp_ids:
        return False, f"Unknown target_temp_id: {tgt}"
    if src == tgt:
        return False, "A node cannot connect to itself."
    if rel not in ALLOWED_RELATIONSHIP_TYPES:
        return False, f"Invalid relationship type: {rel}"

    return True, None