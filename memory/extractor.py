
import json

import requests

from memory.validator import validate_memory_candidate


MODEL = "llama3.2:3b"
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"



EXTRACTION_PROMPT = """
You extract potential long-term memories from journal entries.

Your goal is to identify information that could meaningfully
improve continuity and personalization in future conversations.

IMPORTANT RULES:

1. Preserve the user's actual meaning.
2. Extract only explicitly supported information.
3. Never invent facts, emotions, relationships, or intentions.
4. Prefer complete, concise statements over vague keywords.
5. Distinguish events, states, preferences, topics,
   people, and assertions.
6. Do not turn temporary feelings into permanent traits.
7. Do not infer a profession or identity from one activity.
8. Do not diagnose the user.
9. Treat health, trauma, intimate relationships, and
   particularly private information as highly_sensitive.
10. Do not extract routine daily activities without
    clear continuing relevance.
11. Do not extract isolated details simply because
    they are explicitly mentioned.
12. Prefer information likely to remain useful across
    multiple conversations.
13. Avoid duplicate or overlapping memories.
14. Extract at most five candidates.
15. If nothing is sufficiently useful, return an empty list.

EXAMPLES OF INFORMATION WORTH REMEMBERING:

- Explicit communication preferences.
- Recurring activities or responsibilities.
- Important ongoing projects.
- Meaningful changes in circumstances.
- Explicitly stated long-term goals.

EXAMPLES THAT SHOULD GENERALLY NOT BE REMEMBERED:

- Having coffee on an ordinary evening.
- Watching an unrelated movie.
- A one-time routine activity.
- A temporary detail with no future relevance.

ALLOWED NODE TYPES:

- person
- event
- state
- topic
- assertion
- preference

SENSITIVITY LEVELS:

- normal
- sensitive
- highly_sensitive

Confidence must be between 0 and 1.
It is the model's estimate, not a calibrated probability.

Return valid JSON using exactly this structure:

{
  "memories": [
    {
      "node_type": "preference",
      "content": "The user prefers practical examples when learning.",
      "sensitivity_level": "normal",
      "confidence": 0.9
    }
  ]
}

If nothing is worth remembering:

{
  "memories": []
}

Return JSON only. No Markdown or explanations.
"""


def extract_memory_candidates(entry):
    """
    Ask the local Ollama model to propose memory candidates.

    This function does not write anything to the database.

    Returns:
        A dictionary containing valid candidates and rejected candidates.
    """

    if not isinstance(entry, str) or not entry.strip():
        raise ValueError("Journal entry must be a non-empty string.")

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": EXTRACTION_PROMPT,
                },
                {
                    "role": "user",
                    "content": entry.strip(),
                },
            ],
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.1,
            },
        },
        timeout=180,
    )

    response.raise_for_status()

    response_data = response.json()
    model_output = response_data["message"]["content"]

    parsed_output = json.loads(model_output)

    if not isinstance(parsed_output, dict):
        raise ValueError("Model output must be a JSON object.")

    memories = parsed_output.get("memories")

    if not isinstance(memories, list):
        raise ValueError("'memories' must be a JSON list.")

    valid_candidates = []
    rejected_candidates = []

    for candidate in memories:
        is_valid, error = validate_memory_candidate(candidate)

        if is_valid:
            valid_candidates.append(candidate)
        else:
            rejected_candidates.append({
                "candidate": candidate,
                "reason": error,
            })

    return {
        "valid": valid_candidates,
        "rejected": rejected_candidates,
    }
