
import json
from datetime import datetime
from pathlib import Path

import requests
import streamlit as st


MODEL = "llama3.2:3b"
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
JOURNAL_FILE = Path("journal_entries.json")

SYSTEM_PROMPT = """
You are a reflective journaling companion, not a therapist.

Help the user reflect on their experience.

- Acknowledge the feelings they describe without judging them.
- Reflect only what they have shared. Do not invent details.
- Avoid clichés, forced positivity, and dismissive reassurance.
- Do not rush to give advice or solutions.
- Ask at most one gentle, open-ended question when appropriate.
- Respect the user's choice not to explore an issue further.
- Use natural, concise, warm language.
- Do not diagnose conditions or claim to know exactly how
  the user feels.
- If the user describes immediate danger, encourage them to
  contact emergency services or a trusted person nearby.

Keep your response brief and focused on reflection.
"""


def generate_reflection(entry, emotion):
    """Generate a reflection using the local language model."""

    prompt = f"""
The user's self-described emotion is: {emotion}

Journal entry:
{entry}

Respond naturally and without judgment.
"""

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": {"temperature": 0.5},
        },
        timeout=180,
    )

    response.raise_for_status()
    return response.json()["message"]["content"].strip()


def save_entry(entry, emotion, reflection):
    """Save a journal entry to a local JSON file."""

    if JOURNAL_FILE.exists():
        with JOURNAL_FILE.open("r", encoding="utf-8") as file:
            entries = json.load(file)
    else:
        entries = []

    entries.append({
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "entry": entry,
        "emotion": emotion,
        "reflection": reflection,
    })

    with JOURNAL_FILE.open("w", encoding="utf-8") as file:
        json.dump(entries, file, indent=2, ensure_ascii=False)


st.set_page_config(
    page_title="Reflect",
    page_icon="✦",
    layout="centered",
)

st.title("Reflect")
st.caption("A quiet space to put your thoughts into words.")

st.info(
    "This prototype uses a local Ollama model for responses. "
    "Saving is optional. Saved entries are unencrypted on this computer."
)

with st.form("journal_form"):
    entry = st.text_area(
        "What has been on your mind?",
        placeholder="Write freely. You do not need to organise your thoughts.",
        height=200,
    )

    emotion = st.selectbox(
        "How would you describe your current feeling? (Optional)",
        [
            "Not specified",
            "Overwhelmed",
            "Sad",
            "Anxious",
            "Frustrated",
            "Lonely",
            "Hopeful",
            "Calm",
            "Mixed feelings",
        ],
    )

    save_locally = st.checkbox(
        "Save this entry and response on this computer",
        value=False,
    )

    submitted = st.form_submit_button(
        "Reflect with me",
        use_container_width=True,
    )

if submitted:
    if not entry.strip():
        st.warning("Write a few words before continuing.")
    else:
        try:
            with st.spinner("Taking a moment to reflect..."):
                reflection = generate_reflection(
                    entry.strip(), emotion
                )

            st.session_state["reflection"] = reflection
            st.session_state["last_entry"] = entry.strip()
            st.session_state["last_emotion"] = emotion

            if save_locally:
                save_entry(entry.strip(), emotion, reflection)
                st.session_state["saved"] = True
            else:
                st.session_state["saved"] = False

        except requests.exceptions.ConnectionError:
            st.error(
                "Ollama is not responding. Check that it is running "
                "and that the model is available."
            )
        except requests.exceptions.Timeout:
            st.error(
                "The model took too long to respond. Try again."
            )
        except (
            requests.exceptions.RequestException,
            ValueError,
            KeyError,
        ):
            st.error(
                "The response could not be processed. "
                "Check Ollama and try again."
            )

if "reflection" in st.session_state:
    st.divider()
    st.subheader("A moment to reflect")
    st.write(st.session_state["reflection"])

    if st.session_state.get("saved"):
        st.caption("Your entry and response were saved locally.")

    if st.button("Clear current reflection"):
        for key in (
            "reflection",
            "last_entry",
            "last_emotion",
            "saved",
        ):
            st.session_state.pop(key, None)

        st.rerun()

st.divider()
st.caption(
    "An experimental reflection tool, not a mental health service. "
    "Responses may be inaccurate or unsuitable."
)
