from pathlib import Path

from langchain.agents import create_agent
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI


DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "anime.db"


def make_sql_tool(llm: ChatOpenAI):
    db = SQLDatabase.from_uri(f"sqlite:///{DB_PATH}")
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    sql_agent = create_agent(
        llm,
        toolkit.get_tools(),
        system_prompt=(
            "Всегда включай поле anime.id в SELECT. "
            "Для названий используй колонку anime.russian. "
            "По умолчанию сортируй по anime.score DESC. "
            "Схема БД: "
            "  anime(id, mal_id, name, russian, kind, episodes, duration, status, year, score, rating, description, url, poster_url, trailer_url, franchise); "
            "  genre(id, name), anime_genre(anime_id, genre_id); "
            "  theme(id, name), anime_theme(anime_id, theme_id); "
            "  demographic(id, name), anime_demographic(anime_id, demographic_id); "
            "  studio(id, name), anime_studio(anime_id, studio_id). "
            "Для фильтрации по жанру/теме/демографии/студии используй JOIN. "
            "Пример — аниме жанра Романтика: "
            "SELECT a.id, a.russian FROM anime a "
            "JOIN anime_genre ag ON ag.anime_id = a.id "
            "JOIN genre g ON g.id = ag.genre_id "
            "WHERE g.name = 'Романтика' ORDER BY a.score DESC. "
            "Пример — топ студий: "
            "SELECT s.name, COUNT(*) AS cnt FROM studio s "
            "JOIN anime_studio ast ON ast.studio_id = s.id "
            "GROUP BY s.id ORDER BY cnt DESC. "
            "Все названия жанров/тем/студий на русском языке. "
            "При поиске аниме по названию используй LIKE '%название%', а не точное совпадение. "
            "Отвечай на русском."
        ),
    )

    @tool
    def sql_search(query: str) -> str:
        """
        Ищет аниме в базе данных по SQL-запросу на естественном языке.
        Используй когда:
        - пользователь просит топ, рейтинг, фильтр по году/студии/жанру
          ('топ-5 меха', 'лучшие аниме 2023', 'что снял Madhouse')
        - пользователь упомянул конкретное аниме и нужно получить его описание
          перед поиском похожего ('найди похожее на Берсерк')
        """
        result = sql_agent.invoke({"messages": [{"role": "user", "content": query}]})
        return result["messages"][-1].content

    return sql_search
