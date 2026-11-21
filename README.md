# Reflect — Local Empathetic AI Journaling

### A local-first conversational memory prototype for reflective journaling

This project explores how a locally running language model can support personal reflection by keeping track of a user's context over time, linking related people, events, and emotional shifts in a memory graph, and offering grounded, empathetic responses without sending personal entries to cloud APIs.

Built for human-computer interaction (HCI) research on inspectable, user-controlled AI memory, the app runs locally using **Streamlit**, **SQLite**, and **Ollama**.

---

## Why This Prototype Exists

Many AI tools either treat every prompt in isolation or store memory behind a black box that users cannot inspect or correct—and smaller local models can easily invent connections when given raw text logs.

This prototype explores a more transparent approach:

- **Context grounded in what you wrote:** Instead of feeding raw past entries blindly into every prompt, the system extracts structured memory items (people, events, emotional states, preferences, topics, and assertions) and typed relationships (such as `involved_in`, `contradicts`, `supports`, and `changed_to`) directly from journal entries.
- **User control and visibility:** Memories and relationships are saved in a local SQLite database with approval states (`pending`, `approved`, `rejected`). You can inspect the graph visually, approve or remove items, and see which memories and links were used to form a response.
- **Focused retrieval:** When you ask a question, the app finds relevant approved memories using local embeddings (with a lexical fallback if embeddings are unavailable), stays focused on the matching scenario, and includes directly linked neighboring memories so immediate context is preserved without pulling in unrelated threads.
- **Empathetic, non-directive reflection:** Responses aim to validate feelings, separate observed events from possible interpretations, and suggest gentle, practical ideas tied to what was actually shared.

---

## What You Can Do in the App

The interface (`app.py`) is organized into three tabs:

1. **Journal & Extract:** Write a journal entry and extract structured memories and relationships using `llama3.2:3b` via Ollama. You can let items save and approve automatically or review them one by one.
2. **Explore & Manage Graph:** View your stored memories and relationships in a color-coded graph (`data/memory.db`), filter by approval status, approve pending memories, link two approved memories manually, or delete memories you no longer want.
3. **Ask & Reflect:** Ask a question about your entries and see Reflect's response alongside the matched memories, directly connected neighbors, traversed relationships, and retrieval notes.

---

## Running Locally

### What You Need

- **Python 3.10+**
- **[Ollama](https://ollama.com/)** running locally (`ollama serve`)
- Two local models pulled in Ollama:
  - `llama3.2:3b` for extraction and reflection
  - `nomic-embed-text` for semantic retrieval

### Setup Steps

1. **Pull the local models:**

   ```bash
   ollama pull llama3.2:3b
   ollama pull nomic-embed-text
   ```

2. **Create and activate a virtual environment:**

   ```bash
   python3 -m venv .venv
   ```

   **Linux / macOS:**

   ```bash
   source .venv/bin/activate
   ```

   **Windows:**

   ```bash
   .venv\Scripts\activate
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Start the app:**

   ```bash
   streamlit run app.py
   ```

   This launches the interface locally (typically at `http://localhost:8501`) and creates `data/memory.db` automatically if it does not exist yet.

---

## Privacy, Scope, and Limitations

- **Local-only processing and storage:** Entries are sent only to your local Ollama instance, and memories and links are saved in a local SQLite file (`data/memory.db`) rather than an external cloud service or encrypted store. Avoid putting highly sensitive data in it, especially on shared machines.
- **Small-model trade-offs:** Because extraction and reflections run on a compact 3B model, occasional classification or phrasing slips can happen—which is why review and graph editing controls are built into the UI.
- **Research prototype, not therapy:** This project is an HCI exploration of personal memory and reflection, not a clinical, diagnostic, or mental-health service.

---

## Where It Can Go Next

- **Hosting support:** Adding configurable model endpoints and storage options so the prototype can be hosted later for broader testing or remote studies while keeping local execution as an option.
- **Cross-entry continuity:** Connecting recurring people, topics, and emotional shifts more smoothly across separate journal entries over time.
- **Export and protection:** Adding options to export graph data for qualitative analysis and protect local storage more strongly.