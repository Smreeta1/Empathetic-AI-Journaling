RELATIONSHIP_DESCRIPTIONS = {
    "related_to": "Two memories are meaningfully connected.",
    "involved_in": "A person or memory is involved in an event or situation.",
    "happened_before": "One event happened before another event.",
    "changed_to": "A previous state or situation changed into a later one.",
    "supports": "One memory provides evidence or support for another.",
    "contradicts": "Two memories contain conflicting information.",
}


def escape_dot(value):
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", " ")
    )


def get_node_label(node):
    return f"{node['node_type'].title()}: {node['content'][:65]}"


def create_graph_dot(nodes, edges):
    dot = [
        "digraph Memory {",
        'rankdir="LR";',
        'graph [nodesep=0.7, ranksep=1.0];',
        'node [shape=box, style="rounded,filled", fontname="Arial", fontsize=10];',
        'edge [fontname="Arial", fontsize=9];',
    ]
    for node in nodes:
        label = escape_dot(get_node_label(node))
        if node["approval_status"] == "approved":
            fill_color = "palegreen"
        elif node["approval_status"] == "pending":
            fill_color = "lightgoldenrod"
        else:
            fill_color = "lightgray"
        dot.append(f'"{node["id"]}" [label="{label}", fillcolor="{fill_color}"];')

    for edge in edges:
        label = escape_dot(edge["relationship_type"])
        dot.append(
            f'"{edge["source_node_id"]}" -> "{edge["target_node_id"]}" [label="{label}"];'
        )
    dot.append("}")
    return "\n".join(dot)