import math
import re
import requests

from memory.extractor import OLLAMA_URL
from memory.graph_store import expand_approved_subgraph


EMBEDDING_MODEL = "nomic-embed-text"


def _embed_single(text):
    cleaned = " ".join(str(text).strip().split())
    if not cleaned:
        return []

    base_url = OLLAMA_URL.rsplit("/api/", 1)[0]

    # Try /api/embed first (Ollama >= 0.4)
    try:
        resp = requests.post(
            f"{base_url}/api/embed",
            json={
                "model": EMBEDDING_MODEL,
                "input": cleaned,
                "keep_alive": "30m",
            },
            timeout=25,
        )
        if resp.status_code == 200:
            embeddings = resp.json().get("embeddings")
            if isinstance(embeddings, list) and embeddings and isinstance(embeddings[0], list):
                return embeddings[0]
    except requests.RequestException:
        pass

    # Fallback to /api/embeddings (older Ollama endpoints)
    resp = requests.post(
        f"{base_url}/api/embeddings",
        json={
            "model": EMBEDDING_MODEL,
            "prompt": cleaned,
            "keep_alive": "30m",
        },
        timeout=25,
    )
    resp.raise_for_status()
    vec = resp.json().get("embedding")
    return vec if isinstance(vec, list) else []


def _embed_batch(texts):
    vectors = []
    for t in texts:
        vec = _embed_single(t)
        if not vec:
            return []
        vectors.append(vec)
    return vectors


def _cosine_similarity(vec_a, vec_b):
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _tokenize(text):
    return set(re.findall(r"[a-z0-9]+", str(text).lower()))


def _build_node_representation(node, all_edges, node_lookup):
    parts = [f"{node['node_type']}: {node['content']}"]
    for edge in all_edges:
        if edge["source_node_id"] == node["id"]:
            other = node_lookup.get(edge["target_node_id"])
            if other:
                parts.append(f"{edge['relationship_type']} -> {other['content']}")
        elif edge["target_node_id"] == node["id"]:
            other = node_lookup.get(edge["source_node_id"])
            if other:
                parts.append(f"{other['content']} <- {edge['relationship_type']}")
    return " | ".join(parts)


def _get_connected_components(approved_ids, all_edges):
    adj = {nid: set() for nid in approved_ids}
    for e in all_edges:
        u, v = e["source_node_id"], e["target_node_id"]
        if u in adj and v in adj:
            adj[u].add(v)
            adj[v].add(u)

    visited = set()
    components = []
    for nid in approved_ids:
        if nid in visited:
            continue
        comp = set()
        stack = [nid]
        while stack:
            curr = stack.pop()
            if curr in comp:
                continue
            comp.add(curr)
            stack.extend(adj.get(curr, ()) - comp)
        visited.update(comp)
        components.append(comp)
    return components


def _discriminative_score(question, approved_nodes, all_edges, node_lookup):
    q_tokens = _tokenize(question)
    if not q_tokens:
        return []

    node_tokens = {}
    doc_freq = {}
    n_docs = max(len(approved_nodes), 1)

    for node in approved_nodes:
        rep = _build_node_representation(node, all_edges, node_lookup)
        toks = _tokenize(rep)
        node_tokens[node["id"]] = toks
        for t in toks:
            doc_freq[t] = doc_freq.get(t, 0) + 1

    scored = []
    for node in approved_nodes:
        toks = node_tokens[node["id"]]
        shared = q_tokens.intersection(toks)
        score = 0.0
        for t in shared:
            df = doc_freq.get(t, 1)
            if n_docs > 2 and df / n_docs > 0.6:
                continue
            idf = math.log((n_docs + 1) / (df + 0.5))
            score += max(idf, 0.25)

        content_toks = _tokenize(node["content"])
        for t in q_tokens.intersection(content_toks):
            df = doc_freq.get(t, 1)
            if n_docs <= 2 or df / n_docs <= 0.6:
                score += 1.5 if node["node_type"] == "person" else 0.75

        scored.append((score, node["id"]))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


def retrieve_contextual_subgraph(question, approved_nodes, all_edges, top_k=4):
    """
    Retrieve relevant approved memories using nomic-embed-text semantic similarity
    (with IDF lexical fallback) and isolate to the best-matching connected graph component.
    """
    if not approved_nodes:
        return {
            "direct_matches": [],
            "expanded_memories": [],
            "all_nodes": [],
            "edges": [],
            "reasoning": "No approved memories found.",
            "used_fallback": False,
        }

    approved_ids = {n["id"] for n in approved_nodes}
    node_lookup = {n["id"]: n for n in approved_nodes}
    components = _get_connected_components(approved_ids, all_edges)
    node_to_component = {}
    for idx, comp in enumerate(components):
        for nid in comp:
            node_to_component[nid] = idx

    used_fallback = False

    try:
        reps = [
            _build_node_representation(node, all_edges, node_lookup)
            for node in approved_nodes
        ]
        vectors = _embed_batch([question] + reps)
        if not vectors:
            raise ValueError("Empty embeddings")

        q_vec = vectors[0]
        scored_pairs = [
            (_cosine_similarity(q_vec, n_vec), node["id"])
            for node, n_vec in zip(approved_nodes, vectors[1:])
        ]
        scored_pairs.sort(key=lambda x: x[0], reverse=True)
        positive_matches = [(s, nid) for s, nid in scored_pairs if s >= 0.45]
        method_label = (
            f"Semantic similarity via {EMBEDDING_MODEL} (top score: {round(scored_pairs[0][0], 3)})"
            if scored_pairs
            else f"Semantic similarity via {EMBEDDING_MODEL}"
        )
    except Exception as exc:
        scored_pairs = _discriminative_score(question, approved_nodes, all_edges, node_lookup)
        positive_matches = [(s, nid) for s, nid in scored_pairs if s > 0]
        used_fallback = True
        method_label = f"Lexical fallback ({type(exc).__name__}: {exc})"

    if not positive_matches:
        return {
            "direct_matches": [],
            "expanded_memories": [],
            "all_nodes": [],
            "edges": [],
            "reasoning": "No approved memories matched the concepts in this question.",
            "used_fallback": used_fallback,
        }

    comp_scores = {}
    for s, nid in positive_matches:
        c_idx = node_to_component.get(nid)
        if c_idx is not None:
            prev_max, prev_sum = comp_scores.get(c_idx, (0.0, 0.0))
            comp_scores[c_idx] = (max(prev_max, s), prev_sum + s)

    best_comp_idx = max(
        comp_scores.keys(),
        key=lambda idx: (comp_scores[idx][0], comp_scores[idx][1]),
    )
    best_component_nodes = components[best_comp_idx]

    seed_ids = [
        nid for s, nid in positive_matches if nid in best_component_nodes
    ][:top_k]
    if not seed_ids:
        seed_ids = [next(iter(best_component_nodes))]

    subgraph = expand_approved_subgraph(seed_ids)

    filtered_nodes = [
        n for n in subgraph["nodes"] if n["id"] in best_component_nodes
    ]
    filtered_node_ids = {n["id"] for n in filtered_nodes}
    filtered_edges = [
        e
        for e in subgraph["edges"]
        if e["source_node_id"] in filtered_node_ids
        and e["target_node_id"] in filtered_node_ids
    ]

    seed_set = set(seed_ids)
    direct_matches = [n for n in filtered_nodes if n["id"] in seed_set]
    expanded_memories = [n for n in filtered_nodes if n["id"] not in seed_set]

    reasoning = (
        f"{method_label}; isolated to the matching scenario subgraph "
        f"({len(filtered_nodes)} connected node(s))."
    )

    return {
        "direct_matches": direct_matches,
        "expanded_memories": expanded_memories,
        "all_nodes": filtered_nodes,
        "edges": filtered_edges,
        "reasoning": reasoning,
        "used_fallback": used_fallback,
    }