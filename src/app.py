import os
import time
from dotenv import load_dotenv
import streamlit as st
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from qdrant_client import QdrantClient

from model.agent import AgentSystem

load_dotenv()

st.set_page_config(page_title="Miruku", layout="centered")
st.title("Miruku — поиск и рекомендации аниме тайтлов")


@st.cache_resource
def get_agent() -> AgentSystem:
    llm_fast = ChatOpenAI(
        model="openai/gpt-4.1-mini",
        api_key=os.environ["VSELLM_API_KEY"],
        base_url=os.environ["VSELLM_BASE_URL"],
    )
    llm_quality = ChatOpenAI(
        model="openai/gpt-4.1",
        api_key=os.environ["VSELLM_API_KEY"],
        base_url=os.environ["VSELLM_BASE_URL"],
    )
    embeddings = OpenAIEmbeddings(
        model="google/gemini-embedding-001",
        api_key=os.environ["VSELLM_API_KEY"],
        base_url=os.environ["VSELLM_BASE_URL"],
    )
    qdrant = QdrantClient(
        host=os.environ.get("QDRANT_HOST", "localhost"),
        port=int(os.environ.get("QDRANT_PORT", 6333)),
    )
    return AgentSystem(
        llm_fast=llm_fast,
        llm_quality=llm_quality,
        embeddings=embeddings,
        qdrant_client=qdrant,
        collection_name="anime_storage",
    )


agent = get_agent()

if "messages" not in st.session_state:
    st.session_state.messages = []
if "history" not in st.session_state:
    st.session_state.history = []

# Отображаем историю чата
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant":
            if msg.get("poster_url"):
                st.image(msg["poster_url"], width=300)
            st.markdown(msg["text"])
            if msg.get("url"):
                st.markdown(f"[Открыть на Shikimori]({msg['url']})")
            if msg.get("trailer_url"):
                st.markdown(f"[🎬 Трейлер]({msg['trailer_url']})")
        else:
            st.markdown(msg["content"])

if query := st.chat_input("Опиши что хочешь посмотреть..."):
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        streamed_text = ""
        meta = {}
        placeholder.markdown("_Думаю..._")

        try:
            for chunk in agent.handle_stream(query, st.session_state.history):
                if isinstance(chunk, dict) and "__meta__" in chunk:
                    meta = chunk["__meta__"]
                    st.session_state.history = chunk["__history__"]
                else:
                    for char in chunk:
                        streamed_text += char
                        display = streamed_text.split("---META---")[0]
                        placeholder.markdown(display)
                        time.sleep(0.01)
        except Exception as e:
            st.error(f"Ошибка: {e}")
            raise

        display_text = streamed_text.split("---META---")[0].strip()
        placeholder.markdown(display_text)

        if meta.get("poster_url"):
            st.image(meta["poster_url"], width=300)
        if meta.get("url"):
            st.markdown(f"[Открыть на Shikimori]({meta['url']})")
        if meta.get("trailer_url"):
            st.markdown(f"[🎬 Трейлер]({meta['trailer_url']})")

    st.session_state.messages.append({
        "role": "assistant",
        "text": display_text,
        **meta,
    })
