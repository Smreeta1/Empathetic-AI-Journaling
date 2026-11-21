import requests

from memory.extractor import MODEL, OLLAMA_URL


REFLECTION_SYSTEM_PROMPT = """
You are Reflect, a warm, empathetic, grounded AI journaling companion (not a therapist or clinician).

Answer using ONLY the APPROVED MEMORIES and RELATIONSHIPS provided.
STRICT GROUNDING RULES:
- Never invent people, managers, complaints, workplaces, or events that are not written in the APPROVED MEMORIES below.
- Never transfer a memory from one context to another (for example, if a memory is about a personal message to Sam and does not mention work, do NOT describe it as happening at work).
- If the retrieved memories do not actually answer the context the user asked about, say so clearly and share only what is actually recorded.
- Acknowledge the user's feelings warmly without clichés or diagnosing.
- Separate observed facts/events from possible interpretations.
- Offer 2–3 practical, gentle ideas grounded strictly in what the user actually shared.
"""


def generate_grounded_response(question, bundle):
    nodes = bundle.get("all_nodes", [])
    edges = bundle.get("edges", [])

    if not nodes:
        return (
            "I don't have any approved memories saved about that topic yet. "
            "If you'd like to share a journal entry about it in Tab 1, I can remember it and reflect with you."
        )

    node_lookup = {n["id"]: n for n in nodes}
    memory_lines = [f"- [{n['node_type'].upper()}] {n['content']}" for n in nodes]

    edge_lines = []
    for e in edges:
        src = node_lookup.get(e["source_node_id"])
        tgt = node_lookup.get(e["target_node_id"])
        if src and tgt:
            line = f"- ({src['content']}) --[{e['relationship_type']}]--> ({tgt['content']})"
            if e.get("evidence"):
                line += f" | Evidence: {e['evidence']}"
            edge_lines.append(line)

    context_block = "APPROVED MEMORIES:\n" + "\n".join(memory_lines)
    if edge_lines:
        context_block += "\n\nRELATIONSHIPS:\n" + "\n".join(edge_lines)

    user_prompt = (
        f"{context_block}\n\n"
        f"USER QUESTION:\n{question.strip()}\n\n"
        "Respond concisely, empathetically, and strictly from the approved memories above."
    )

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "keep_alive": "30m",
            "messages": [
                {"role": "system", "content": REFLECTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {
                "temperature": 0.25,
                "num_predict": 380,
            },
        },
        timeout=90,
    )
    response.raise_for_status()
    return response.json()["message"]["content"].strip()