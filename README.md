# Local Empathetic-AI-Journaling

### A local-first prototype for reflective journaling

This project explores how a locally running language model can support personal reflection through emotionally considerate, non-directive responses.

The application uses **Streamlit** for the interface and **Ollama** for local language-model inference. Users can write a journal entry, optionally describe their current emotion, and receive a reflective response.

## Features

- **Local language-model inference** through Ollama
- **Reflective prompting** focused on emotional validation, reflection, and user autonomy
- **Optional journal storage** on the local machine
- **Interactive interface** built with Streamlit
- **Qualitative evaluation** of response behavior

## Getting Started

### Prerequisites

- Python
- [Ollama](https://ollama.com/)
- A compatible local language model

### Installation

1. Download a compatible model:

   ```bash
   ollama pull llama3.2:3b
   ```

2. Create a Python virtual environment:

   ```bash
   python3 -m venv .venv
   ```

3. Activate the environment.

   **Linux/macOS:**

   ```bash
   source .venv/bin/activate
   ```

   **Windows:**

   ```bash
   .venv\Scripts\activate
   ```

4. Install the project dependencies:

   ```bash
   pip install -r requirements.txt
   ```

5. Start the application:

   ```bash
   streamlit run app.py
   ```

## Privacy and Limitations

Journal entries are sent to the locally running Ollama endpoint for inference. The prototype is not designed to send journal content to a hosted AI inference API.

If journal entries are saved, they are stored as **unencrypted JSON files** on the local machine. Avoid entering sensitive personal information, and protect any saved files appropriately.

The model may generate inaccurate, generic, or unsuitable responses. This project is an experimental reflection tool, not a diagnostic or therapeutic service.

## Evaluation Direction

A small qualitative review can examine whether generated responses:

- Acknowledge the feelings explicitly described by the user
- Avoid unsupported assumptions about the user's experiences
- Respect the user's autonomy and perspective
- Avoid unsolicited advice
- Maintain a reflective and emotionally considerate tone

This project does not claim clinical effectiveness or present findings from a generalizable user study.

## Technologies

- Python
- Streamlit
- Ollama
- Locally running language models
- JSON for optional journal storage
