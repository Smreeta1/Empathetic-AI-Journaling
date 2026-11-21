import json
import requests

from memory.validator import (
    sanitize_candidate,
    validate_extracted_relationship,
    validate_memory_candidate,
)


MODEL = "llama3.2:3b"
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"


EXTRACTION_PROMPT = """
Extract key memories (people, events, states, preferences, topics, assertions) and their relationships from the journal entry.
Stay strictly faithful ONLY to what is written. Never invent facts.

Node types:
- person: ONLY a person's name or role (e.g., "Colleague", "Manager", "Sam"). Extract EVERY person or role mentioned!
- event: a specific action, conversation, praise, complaint, or incident.
- state: an emotional or situational state (e.g., "Feeling confused by inconsistent behavior").
- preference: a stated preference, dislike, or boundary.
- topic: a core subject or relationship area.
- assertion: a key statement or truth shared by the user.

Relationship types (connect people to their events and states):
- involved_in: person -> event or state
- contradicts: conflicting events or behaviors
- supports: event/assertion -> state
- changed_to: earlier state/situation -> later state/situation
- happened_before: earlier event -> later event
- related_to: meaningfully connected items

Return valid JSON only:
{
  "memories": [
    {"temp_id": "m1", "node_type": "person", "content": "Colleague", "sensitivity_level": "normal", "confidence": 0.9},
    {"temp_id": "m2", "node_type": "person", "content": "Manager", "sensitivity_level": "normal", "confidence": 0.9},
    {"temp_id": "m3", "node_type": "event", "content": "Colleague praised the user in front of other people.", "sensitivity_level": "normal", "confidence": 0.9},
    {"temp_id": "m4", "node_type": "event", "content": "Colleague complained about the user to the manager.", "sensitivity_level": "sensitive", "confidence": 0.9},
    {"temp_id": "m5", "node_type": "state", "content": "User felt confused by the colleague's inconsistent behavior.", "sensitivity_level": "sensitive", "confidence": 0.9}
  ],
  "relationships": [
    {"source_temp_id": "m1", "target_temp_id": "m3", "relationship_type": "involved_in", "evidence": "Colleague praised the user publicly."},
    {"source_temp_id": "m1", "target_temp_id": "m4", "relationship_type": "involved_in", "evidence": "Colleague made the complaint."},
    {"source_temp_id": "m2", "target_temp_id": "m4", "relationship_type": "involved_in", "evidence": "Complaint was made to the manager."},
    {"source_temp_id": "m3", "target_temp_id": "m4", "relationship_type": "contradicts", "evidence": "Public praise vs private complaint."}
  ]
}
"""


def extract_memory_candidates(entry):
    if not isinstance(entry, str) or not entry.strip():
        raise ValueError("Journal entry must be a non-empty string.")

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "keep_alive": "30m",
            "messages": [
                {"role": "system", "content": EXTRACTION_PROMPT},
                {"role": "user", "content": entry.strip()},
            ],
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 1000,
            },
        },
        timeout=90,
    )
    response.raise_for_status()

    parsed_output = json.loads(response.json()["message"]["content"])
    if not isinstance(parsed_output, dict):
        raise ValueError("Model output must be a JSON object.")

    memories = parsed_output.get("memories")
    if not isinstance(memories, list):
        raise ValueError("'memories' must be a JSON list.")

    relationships = parsed_output.get("relationships", [])
    if not isinstance(relationships, list):
        relationships = []

    valid_candidates = []
    rejected_candidates = []
    valid_temp_ids = set()

    for idx, raw_candidate in enumerate(memories[:7]):
        candidate = sanitize_candidate(raw_candidate)
        if isinstance(candidate, dict) and not candidate.get("temp_id"):
            candidate["temp_id"] = f"m{idx + 1}"

        is_valid, error = validate_memory_candidate(candidate)
        if is_valid:
            valid_candidates.append(candidate)
            valid_temp_ids.add(candidate["temp_id"])
        else:
            rejected_candidates.append({"candidate": candidate, "reason": error})

    valid_relationships = []
    rejected_relationships = []

    for rel in relationships[:10]:
        is_valid, error = validate_extracted_relationship(rel, valid_temp_ids)
        if is_valid:
            valid_relationships.append({
                "source_temp_id": rel["source_temp_id"],
                "target_temp_id": rel["target_temp_id"],
                "relationship_type": rel["relationship_type"],
                "evidence": (rel.get("evidence") or "").strip() or None,
            })
        else:
            rejected_relationships.append({"candidate": rel, "reason": error})

    return {
        "valid": valid_candidates,
        "rejected": rejected_candidates,
        "relationships": valid_relationships,
        "rejected_relationships": rejected_relationships,
    }