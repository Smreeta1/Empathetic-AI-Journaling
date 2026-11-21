import requests
import streamlit as st

from memory.extractor import extract_memory_candidates
from memory.graph_store import (
    add_edge,
    add_node,
    approve_all_pending_nodes,
    approve_node,
    delete_all_graph_data,
    delete_node,
    get_all_edges,
    get_all_nodes,
    get_approved_nodes,
    reject_node,
    save_journal_entry,
)
from memory.responder import generate_grounded_response
from memory.retriever import retrieve_contextual_subgraph
from memory.schema import initialize_database
from memory.validator import ALLOWED_RELATIONSHIP_TYPES
from memory.visualizer import (
    RELATIONSHIP_DESCRIPTIONS,
    create_graph_dot,
    get_node_label,
)


@st.fragment
def _render_memory_cards(visible_nodes, nodes, edges):
    node_by_id = {n["id"]: n for n in nodes}
    for node in visible_nodes:
        connected = [
            e for e in edges
            if e["source_node_id"] == node["id"] or e["target_node_id"] == node["id"]
        ]
        with st.container(border=True):
            st.markdown(f"**{node['node_type'].title()}**")
            st.write(node["content"])
            st.caption(
                f"Status: {node['approval_status']} | "
                f"Sensitivity: {node['sensitivity_level']} | "
                f"Confidence: {node['confidence']} | "
                f"Links: {len(connected)}"
            )
            for e in connected:
                if e["source_node_id"] == node["id"]:
                    other = node_by_id.get(e["target_node_id"])
                    st.caption(f"→ `{e['relationship_type']}` → {other['content'] if other else e['target_node_id']}")
                else:
                    other = node_by_id.get(e["source_node_id"])
                    st.caption(f"← `{e['relationship_type']}` ← {other['content'] if other else e['source_node_id']}")

            col_a, col_d = st.columns([1.2, 2.5])
            if node["approval_status"] == "pending":
                if col_a.button("Approve memory", key=f"g_app_{node['id']}"):
                    approve_node(node["id"])
                    st.rerun(scope="fragment")
            if col_d.button(f"Delete memory ({len(connected)} link(s))", key=f"g_del_{node['id']}"):
                try:
                    delete_node(node["id"])
                    st.rerun(scope="fragment")
                except Exception as exc:
                    st.error(f"Could not delete node: {exc}")



st.set_page_config(
    page_title="Reflect — Conversational Memory",
    page_icon="🧠",
    layout="wide",
)

initialize_database()

st.title("Reflect — Conversational Memory")
st.caption(
    "A local-first journaling companion for remembering personal experiences, "
    "connecting relationships and changes over time, and offering grounded reflections."
)
st.info(
    "Research prototype only. Not a mental-health or clinical service. "
    "All extraction and reflections run locally via Ollama."
)

for key, default in {
    "memory_candidates": [],
    "rejected_candidates": [],
    "proposed_relationships": [],
    "current_entry_id": None,
    "retrieval_results": None,
    "generated_answer": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


def _persist_proposed_relationships():
    temp_to_db_id = {
        c["temp_id"]: c["saved_id"]
        for c in st.session_state.memory_candidates
        if c.get("temp_id") and c.get("saved_id")
    }
    for rel in st.session_state.proposed_relationships:
        if rel.get("saved"):
            continue
        src_db = temp_to_db_id.get(rel["source_temp_id"])
        tgt_db = temp_to_db_id.get(rel["target_temp_id"])
        if src_db and tgt_db and src_db != tgt_db:
            add_edge(src_db, tgt_db, rel["relationship_type"], evidence=rel.get("evidence"))
            rel["saved"] = True


tab_extract, tab_graph, tab_retrieve = st.tabs([
    "1. Journal & extract",
    "2. Explore & manage graph",
    "3. Ask & reflect",
])


# =========================================================
# TAB 1: JOURNAL & EXTRACT MEMORIES
# =========================================================
with tab_extract:
    st.subheader("Journal entry & automatic memory + relationship extraction")

    default_entry = (
        "A colleague praises me in front of other people "
        "but later complains about me to our manager. "
        "I feel confused because their behavior seems inconsistent."
    )
    entry = st.text_area(
        "Write a journal entry about any life situation",
        value=default_entry,
        height=150,
        key="journal_input",
    )

    auto_save_and_approve = st.checkbox(
        "Automatically save, approve, and link extracted memories & relationships",
        value=True,
    )

    if st.button("Extract & save memories", type="primary"):
        if not entry.strip():
            st.warning("Please write a journal entry first.")
        else:
            with st.spinner("Extracting memories and relationships via Ollama..."):
                try:
                    entry_id = save_journal_entry(entry)
                    st.session_state.current_entry_id = entry_id

                    result = extract_memory_candidates(entry)
                    valid_list = result["valid"]
                    rel_list = result["relationships"]

                    if auto_save_and_approve:
                        for candidate in valid_list:
                            node_id = add_node(
                                node_type=candidate["node_type"],
                                content=candidate["content"],
                                source_entry_id=entry_id,
                                sensitivity_level=candidate["sensitivity_level"],
                                confidence=candidate["confidence"],
                                auto_approve=True,
                            )
                            candidate["saved_id"] = node_id
                            candidate["approval_status"] = "approved"

                    st.session_state.memory_candidates = valid_list
                    st.session_state.rejected_candidates = result["rejected"]
                    st.session_state.proposed_relationships = rel_list

                    if auto_save_and_approve:
                        _persist_proposed_relationships()
                        st.success(
                            f"Saved & approved {len(valid_list)} memories and linked "
                            f"{len(rel_list)} relationships in your database."
                        )
                    else:
                        st.success(
                            f"Extracted {len(valid_list)} memories and {len(rel_list)} relationships."
                        )
                except requests.exceptions.ConnectionError:
                    st.error("Cannot connect to Ollama. Make sure Ollama is running.")
                except Exception as error:
                    st.error(f"Extraction failed: {error}")

    candidates = st.session_state.memory_candidates
    if candidates:
        st.divider()
        st.subheader("Extracted memories")
        for index, candidate in enumerate(candidates):
            with st.container(border=True):
                temp_tag = f" ({candidate['temp_id']})" if candidate.get("temp_id") else ""
                st.markdown(f"**{candidate['node_type'].title()}** — Candidate {index + 1}{temp_tag}")
                st.write(candidate["content"])
                c1, c2, c3 = st.columns(3)
                c1.caption(f"Type: {candidate['node_type']}")
                c2.caption(f"Sensitivity: {candidate['sensitivity_level']}")
                c3.caption(f"Confidence: {candidate['confidence']}")

                saved_id = candidate.get("saved_id")
                if saved_id:
                    status = candidate.get("approval_status", "pending")
                    st.caption(f"Status: {status}")
                    if status == "pending":
                        b1, b2 = st.columns(2)
                        if b1.button("Approve", key=f"app_{index}_{saved_id}"):
                            if approve_node(saved_id):
                                candidate["approval_status"] = "approved"
                                _persist_proposed_relationships()
                                st.rerun()
                        if b2.button("Reject", key=f"rej_{index}_{saved_id}"):
                            if reject_node(saved_id):
                                candidate["approval_status"] = "rejected"
                                st.rerun()
                else:
                    if st.button("Save memory", key=f"sav_{index}"):
                        node_id = add_node(
                            node_type=candidate["node_type"],
                            content=candidate["content"],
                            source_entry_id=st.session_state.current_entry_id,
                            sensitivity_level=candidate["sensitivity_level"],
                            confidence=candidate["confidence"],
                            auto_approve=True,
                        )
                        candidate["saved_id"] = node_id
                        candidate["approval_status"] = "approved"
                        _persist_proposed_relationships()
                        st.rerun()

        if st.session_state.proposed_relationships:
            st.markdown("#### Extracted relationships")
            temp_lookup = {
                c["temp_id"]: c["content"]
                for c in candidates
                if c.get("temp_id")
            }
            for rel in st.session_state.proposed_relationships:
                src_text = temp_lookup.get(rel["source_temp_id"], rel["source_temp_id"])
                tgt_text = temp_lookup.get(rel["target_temp_id"], rel["target_temp_id"])
                state_txt = "Linked" if rel.get("saved") else "Awaiting node save"
                st.caption(f"• **{src_text}** —[`{rel['relationship_type']}`]→ **{tgt_text}** ({state_txt})")


# =========================================================
# TAB 2: EXPLORE & MANAGE GRAPH
# =========================================================
with tab_graph:
    st.subheader("Persistent memory graph (data/memory.db)")
    nodes = get_all_nodes()
    edges = get_all_edges()
    pending_nodes = [n for n in nodes if n["approval_status"] == "pending"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total memories", len(nodes))
    c2.metric("Approved", sum(n["approval_status"] == "approved" for n in nodes))
    c3.metric("Pending", len(pending_nodes))
    c4.metric("Total links", len(edges))

    if pending_nodes and st.button(f"Approve all {len(pending_nodes)} pending memories now"):
        approve_all_pending_nodes()
        st.rerun()

    if nodes:
        graph_filter = st.selectbox(
            "Display memories",
            ["All memories", "Approved memories", "Pending memories", "Rejected memories"],
        )
        status_map = {
            "All memories": None,
            "Approved memories": "approved",
            "Pending memories": "pending",
            "Rejected memories": "rejected",
        }
        selected_status = status_map[graph_filter]
        visible_nodes = [
            n for n in nodes
            if selected_status is None or n["approval_status"] == selected_status
        ]
        visible_ids = {n["id"] for n in visible_nodes}
        visible_edges = [
            e for e in edges
            if e["source_node_id"] in visible_ids and e["target_node_id"] in visible_ids
        ]

        st.graphviz_chart(create_graph_dot(visible_nodes, visible_edges), width="stretch")
        st.caption("Green = approved · Yellow = pending · Gray = rejected")

        node_by_id = {n["id"]: n for n in nodes}
        for node in visible_nodes:
            connected = [
                e for e in edges
                if e["source_node_id"] == node["id"] or e["target_node_id"] == node["id"]
            ]
            with st.container(border=True):
                st.markdown(f"**{node['node_type'].title()}**")
                st.write(node["content"])
                st.caption(
                    f"Status: {node['approval_status']} | "
                    f"Sensitivity: {node['sensitivity_level']} | "
                    f"Confidence: {node['confidence']} | "
                    f"Links: {len(connected)}"
                )
                for e in connected:
                    if e["source_node_id"] == node["id"]:
                        other = node_by_id.get(e["target_node_id"])
                        st.caption(f"→ `{e['relationship_type']}` → {other['content'] if other else e['target_node_id']}")
                    else:
                        other = node_by_id.get(e["source_node_id"])
                        st.caption(f"← `{e['relationship_type']}` ← {other['content'] if other else e['source_node_id']}")

                col_a, col_d = st.columns([1.2, 2.5])
                if node["approval_status"] == "pending":
                    if col_a.button("Approve memory", key=f"g_app_{node['id']}"):
                        approve_node(node["id"])
                        st.rerun()
                if col_d.button(f"Delete memory ({len(connected)} link(s))", key=f"g_del_{node['id']}"):
                    delete_node(node["id"])
                    st.rerun()

    approved_nodes = [n for n in nodes if n["approval_status"] == "approved"]
    if len(approved_nodes) >= 2:
        with st.expander("Optional: Connect two approved memories manually"):
            labels = {n["id"]: get_node_label(n) for n in approved_nodes}
            src_id = st.selectbox("Source memory", list(labels.keys()), format_func=lambda v: labels[v], key="m_src")
            tgt_opts = [nid for nid in labels if nid != src_id]
            tgt_id = st.selectbox("Target memory", tgt_opts, format_func=lambda v: labels[v], key="m_tgt")
            rel_type = st.selectbox(
                "Relationship type",
                sorted(ALLOWED_RELATIONSHIP_TYPES),
                format_func=lambda v: f"{v} — {RELATIONSHIP_DESCRIPTIONS[v]}",
            )
            ev_text = st.text_input("Evidence (optional)", key="m_ev")
            if st.button("Add relationship"):
                add_edge(src_id, tgt_id, rel_type, evidence=ev_text or None)
                st.rerun()

    if nodes or edges:
        st.divider()
        with st.expander("Reset / delete all memories & relationships in database"):
            confirm_wipe = st.checkbox("I understand this will delete all stored memories and links", key="confirm_wipe")
            if st.button("Delete all memories & links", disabled=not confirm_wipe):
                delete_all_graph_data()
                st.session_state.retrieval_results = None
                st.session_state.generated_answer = None
                st.rerun()


# =========================================================
# TAB 3: ASK & REFLECT USING MEMORY
# =========================================================
with tab_retrieve:
    st.subheader("Contextual graph retrieval & empathetic reflection")
    st.caption(
        "Retrieves matching approved memories and 1-hop graph neighbors in your database, "
        "and generates a grounded reflection and ideas. (Reads memories only; never deletes data.)"
    )

    question = st.text_input(
        "Ask a question",
        placeholder="Who made the complaint? / Who was the complaint made to? / What did the colleague say publicly?",
        key="memory_question",
    )

    b1, b2 = st.columns([2, 1])
    with b1:
        ask_clicked = st.button("Ask using memory", type="primary", width="stretch")
    with b2:
        if st.button("Clear displayed answer", width="stretch"):
            st.session_state.retrieval_results = None
            st.session_state.generated_answer = None
            st.rerun()

    if ask_clicked:
        if not question.strip():
            st.warning("Please enter a question.")
        else:
            approved_memories = get_approved_nodes()
            all_db_edges = get_all_edges()
            bundle = retrieve_contextual_subgraph(question, approved_memories, all_db_edges)
            st.session_state.retrieval_results = bundle
            st.session_state.generated_answer = None

            with st.spinner("Generating grounded response from retrieved subgraph..."):
                try:
                    st.session_state.generated_answer = generate_grounded_response(question, bundle)
                except requests.exceptions.ConnectionError:
                    st.error("Cannot connect to Ollama for response generation.")
                except Exception as error:
                    st.error(f"Response generation failed: {error}")

    bundle = st.session_state.retrieval_results
    if bundle is not None:
        st.divider()
        if st.session_state.generated_answer:
            st.markdown("### Reflect's response")
            with st.container(border=True):
                st.write(st.session_state.generated_answer)

        if bundle.get("reasoning"):
            st.caption(f"Retrieval rationale: {bundle['reasoning']}")

        if bundle["direct_matches"]:
            st.markdown("### Matched memories")
            for m in bundle["direct_matches"]:
                with st.container(border=True):
                    st.write(m["content"])
                    st.caption(f"Type: {m['node_type']}")

        if bundle["expanded_memories"]:
            st.markdown("### Connected graph memories (1-hop expansion)")
            for m in bundle["expanded_memories"]:
                with st.container(border=True):
                    st.write(m["content"])
                    st.caption(f"Type: {m['node_type']} | Connected via approved relationship")

        if bundle["edges"]:
            st.markdown("### Used relationships")
            lookup = {n["id"]: n for n in bundle["all_nodes"]}
            for e in bundle["edges"]:
                s = lookup.get(e["source_node_id"])
                t = lookup.get(e["target_node_id"])
                if s and t:
                    ev = f" — Evidence: {e['evidence']}" if e.get("evidence") else ""
                    st.caption(f"• {s['content']} —[`{e['relationship_type']}`]→ {t['content']}{ev}")