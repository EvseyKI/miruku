import json
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from qdrant_client import QdrantClient

from model.prompt import PROMPT_ENTITY_MEMORY, SYSTEM_PROMPT
from tools.qdrant_search import make_qdrant_tool
from tools.shikimori_ongoings import make_shikimori_similar_tool, make_shikimori_tool
from tools.sql_search import make_sql_tool
from tools.web_search import make_web_search_tool


MEMORY_WINDOW = 6


class AgentSystem:
    def __init__(
        self,
        llm_fast: ChatOpenAI,
        llm_quality: ChatOpenAI,
        embeddings: OpenAIEmbeddings,
        qdrant_client: QdrantClient,
        collection_name: str,
    ):
        self._qdrant_tool, self._set_qdrant_history = make_qdrant_tool(
            llm=llm_fast,
            embeddings=embeddings,
            qdrant_client=qdrant_client,
            collection_name=collection_name,
        )
        sql_tool = make_sql_tool(llm=llm_fast)
        web_tool = make_web_search_tool()
        shikimori_tool = make_shikimori_tool()
        shikimori_similar_tool = make_shikimori_similar_tool()

        tools = [self._qdrant_tool, sql_tool, web_tool, shikimori_tool, shikimori_similar_tool]
        self._agent = create_agent(
            model=llm_quality,
            tools=tools,
            system_prompt=SYSTEM_PROMPT,
        )
        self._qdrant = qdrant_client
        self._collection = collection_name
        self._memory_llm = llm_fast

    def _fetch_meta(self, anime_id: int) -> dict:
        points = self._qdrant.retrieve(
            collection_name=self._collection,
            ids=[anime_id],
            with_payload=True,
        )
        if not points:
            return {}
        payload = points[0].payload
        return {
            "poster_url": payload.get("poster_url"),
            "url": payload.get("url"),
            "trailer_url": payload.get("trailer_url"),
        }

    def _compress(self, response: str) -> str:
        """Сжимает ответ агента до короткой сущности для памяти."""
        try:
            messages = PROMPT_ENTITY_MEMORY.format_messages(response=response)
            result = self._memory_llm.invoke(messages)
            return result.content.strip()
        except Exception:
            return ""

    def handle_stream(self, query: str, history: list[str] | None = None):
        """
        Стримит токены финального ответа агента, затем возвращает метаданные.
        """
        if history is None:
            history = []

        messages = []
        if history:
            memory_text = "\n".join(f"- {h}" for h in history)
            messages.append({
                "role": "system",
                "content": f"Контекст предыдущего диалога:\n{memory_text}",
            })
        messages.append({"role": "user", "content": query})

        self._set_qdrant_history(history)
        full_content = ""
        for chunk in self._agent.stream({"messages": messages}):
            agent_chunk = chunk.get("model")
            if agent_chunk:
                for msg in agent_chunk.get("messages", []):
                    token = msg.content if hasattr(msg, "content") else ""
                    if token and isinstance(token, str):
                        full_content += token
                        yield token

        if "---META---" in full_content:
            text_part, meta_part = full_content.split("---META---", 1)
            try:
                anime_id = int(json.loads(meta_part.strip())["id"])
                meta = self._fetch_meta(anime_id) if anime_id > 0 else {}
            except Exception:
                meta = {}
            response_text = text_part.strip()
        else:
            meta = {}
            response_text = full_content.strip()

        entity = self._compress(response_text)
        if entity:
            history = (history + [entity])[-MEMORY_WINDOW:]

        yield {"__meta__": meta, "__history__": history}

    def handle(self, query: str, history: list[str] | None = None) -> tuple[dict, list[str]]:
        """Обрабатывает запрос пользователя."""
        if history is None:
            history = []

        messages = []
        if history:
            memory_text = "\n".join(f"- {h}" for h in history)
            messages.append({
                "role": "system",
                "content": f"Контекст предыдущего диалога:\n{memory_text}",
            })
        messages.append({"role": "user", "content": query})

        self._set_qdrant_history(history)
        result = self._agent.invoke({"messages": messages})
        content = result["messages"][-1].content

        if "---META---" in content:
            text_part, meta_part = content.split("---META---", 1)
            try:
                anime_id = int(json.loads(meta_part.strip())["id"])
                meta = self._fetch_meta(anime_id) if anime_id > 0 else {}
            except Exception:
                meta = {}
            response_text = text_part.strip()
        else:
            meta = {}
            response_text = content.strip()

        entity = self._compress(response_text)
        if entity:
            history = (history + [entity])[-MEMORY_WINDOW:]

        return {"text": response_text, **meta}, history
