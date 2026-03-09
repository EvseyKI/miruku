from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.tools import tool


def make_web_search_tool():
    search = DuckDuckGoSearchRun()

    @tool
    def web_search(query: str) -> str:
        """
        Ищет в интернете описание фильма, сериала, книги или игры по названию.
        Используй ТОЛЬКО когда пользователь упомянул произведение НЕ из аниме
        (голливудский фильм, сериал, игра), и sql_search не нашёл его в базе.
        Передай результат в qdrant_search для поиска похожего аниме.

        Формат запроса: "<название> фильм описание сюжет жанры атмосфера"
        """
        return search.run(query)

    return web_search
