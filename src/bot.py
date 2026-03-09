import asyncio
import json
import os
import logging
import sqlite3
from functools import partial
from pathlib import Path
from dotenv import load_dotenv

from telegram import Update, LinkPreviewOptions
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from qdrant_client import QdrantClient

from model.agent import AgentSystem

load_dotenv()
logging.basicConfig(level=logging.INFO)

_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "histories.db"

def _init_db():
    with sqlite3.connect(_DB_PATH) as con:
        con.execute(
            "CREATE TABLE IF NOT EXISTS histories "
            "(user_id INTEGER PRIMARY KEY, history TEXT NOT NULL)"
        )

def _load_history(user_id: int) -> list[str]:
    with sqlite3.connect(_DB_PATH) as con:
        row = con.execute(
            "SELECT history FROM histories WHERE user_id = ?", (user_id,)
        ).fetchone()
    return json.loads(row[0]) if row else []

def _save_history(user_id: int, history: list[str]) -> None:
    with sqlite3.connect(_DB_PATH) as con:
        con.execute(
            "INSERT INTO histories(user_id, history) VALUES(?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET history = excluded.history",
            (user_id, json.dumps(history, ensure_ascii=False)),
        )

_init_db()

#TODO: Протестить модели подешевле
llm_fast = ChatOpenAI(
    model="openai/gpt-4.1-mini", # Пока вернул модель побольше, лучше справляется.
    api_key=os.environ["VSELLM_API_KEY"],
    base_url=os.environ["VSELLM_BASE_URL"],
)

llm_quality = ChatOpenAI(
    model="openai/gpt-4.1-mini",
    api_key=os.environ["VSELLM_API_KEY"],
    base_url=os.environ["VSELLM_BASE_URL"],
)

embeddings = OpenAIEmbeddings(
    model="google/gemini-embedding-001",
    api_key=os.environ["VSELLM_API_KEY"],
    base_url=os.environ["VSELLM_BASE_URL"],
)

qdrant_url = os.environ.get("QDRANT_URL")
if qdrant_url:
    qdrant = QdrantClient(url=qdrant_url, api_key=os.environ.get("QDRANT_API_KEY"))
else:
    qdrant = QdrantClient(
        host=os.environ.get("QDRANT_HOST", "localhost"),
        port=int(os.environ.get("QDRANT_PORT", 6333)),
    )

agent = AgentSystem(
    llm_fast=llm_fast,
    llm_quality=llm_quality,
    embeddings=embeddings,
    qdrant_client=qdrant,
    collection_name="anime_storage",
)

async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я Miruku — бот для поиска аниме.\n\n"
        "Просто опиши что хочешь посмотреть своими словами, и я подберу что-нибудь подходящее."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    user_id = update.effective_user.id
    await update.message.chat.send_action("typing")

    # По потокам разобьем
    history = _load_history(user_id)
    loop = asyncio.get_event_loop()
    result, history = await loop.run_in_executor(
        None, partial(agent.handle, query, history)
    )
    _save_history(user_id, history)

    no_preview = LinkPreviewOptions(is_disabled=True)

    text = result["text"]
    if result.get("url"):
        text += f"\n\n🔗 {result['url']}"

    if result.get("poster_url"):
        await update.message.reply_photo(
            photo=result["poster_url"],
            caption=text,
        )
    else:
        await update.message.reply_text(
            text,
            link_preview_options=no_preview,
        )

    if result.get("trailer_url"):
        await update.message.reply_text(f"🎬 Трейлер: {result['trailer_url']}")


if __name__ == "__main__":
    app = ApplicationBuilder().token(os.environ["TELEGRAM_BOT_TOKEN"]).build()
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
