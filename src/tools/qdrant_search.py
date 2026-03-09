from langchain_core.tools import tool
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from qdrant_client import QdrantClient

from tools.vector_db_search import VectorDBSearch


def _format_results(results: list[dict]) -> str:
    lines = []
    for i, r in enumerate(results):
        lines.append(
            f"[{i}] id={r.get('id', '')} {r.get('russian', '')}\n"
            f"Жанры: {', '.join(r.get('genres') or [])}\n"
            f"Темы: {', '.join(r.get('themes') or [])}\n"
            f"Рейтинг: {r.get('score', '')}\n"
            f"Описание: {r.get('description', '')[:400]}\n"
        )
    return "\n".join(lines)


def make_qdrant_tool(
    llm: ChatOpenAI,
    embeddings: OpenAIEmbeddings,
    qdrant_client: QdrantClient,
    collection_name: str,
):
    search = VectorDBSearch(
        llm=llm,
        embeddings=embeddings,
        qdrant_client=qdrant_client,
        collection_name=collection_name,
        top_k=5,
    )
    history_ref: list[str] = []

    @tool
    def qdrant_search(query: str) -> str:
        """
        Ищет аниме по смыслу, атмосфере, теме, сюжету.
        Используй когда пользователь описывает предпочтения своими словами,
        или когда уже извлёк ключевые темы/атмосферу из другого тула.

        НЕ используй напрямую если пользователь упомянул конкретное аниме —
        сначала получи его описание через sql, потом передай сюда.
        НЕ используй напрямую если пользователь упомянул фильм или сериал —
        сначала получи описание через web_search, потом передай сюда.

        Входные данные: ключевые слова, темы, атмосфера, негативные фильтры.
        Без собственных имён — только смысл и ощущение.

        Примеры входных данных:
        'мрачная атмосфера, психологическое давление, без фансервиса'
        'дружба и потери, фэнтези, медленный темп'
        """
        results = search.search(query, history=history_ref or None)
        if not results:
            return "Ничего не найдено."
        return _format_results(results)

    def set_history(h: list[str]) -> None:
        history_ref.clear()
        history_ref.extend(h)

    return qdrant_search, set_history
