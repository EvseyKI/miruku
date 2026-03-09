import os
import re
import httpx
from langchain_core.tools import tool


_BASE_URL = os.environ.get("SHIKI_BASE_HOST", "https://shikimori.one")
_HEADERS = {"User-Agent": "miruku"}

_SEASON_MAP = {
    "зим": "winter", "winter": "winter",
    "весн": "spring", "spring": "spring",
    "лет": "summer", "summer": "summer",
    "осен": "fall",  "осень": "fall", "fall": "fall", "autumn": "fall",
}


def _fetch_animes(params: dict, limit: int = 10) -> list[dict]:
    with httpx.Client() as client:
        response = client.get(
            f"{_BASE_URL}/api/animes",
            params={"order": "ranked", "limit": limit, "censored": "true", **params},
            headers=_HEADERS,
        )
        response.raise_for_status()
        return response.json()


def _parse_season(query: str) -> str | None:
    """Извлекает season-параметр вида '2024_fall' из текста запроса."""
    q = query.lower()
    year_match = re.search(r"\b(20\d{2})\b", q)
    year = year_match.group(1) if year_match else None

    season = None
    for ru, en in _SEASON_MAP.items():
        if ru in q:
            season = en
            break

    if year and season:
        return f"{year}_{season}"
    if year:
        return year  # Shikimori принимает просто год
    return None


def _format(items: list[dict]) -> str:
    lines = []
    for i, a in enumerate(items, 1):
        name = a.get("russian") or a.get("name", "—")
        score = a.get("score", "—")
        episodes = a.get("episodes") or a.get("episodes_aired", "?")
        kind = a.get("kind", "")
        aired = (a.get("aired_on") or "")[:4]
        lines.append(f"{i}. {name} ({kind}, {aired}) — оценка: {score}, эпизодов: {episodes}")
    return "\n".join(lines)


def _fetch_similar(anime_id: int | str, limit: int = 10) -> list[dict]:
    with httpx.Client() as client:
        response = client.get(
            f"{_BASE_URL}/api/animes/{anime_id}/similar",
            headers=_HEADERS,
        )
        response.raise_for_status()
        return response.json()[:limit]

# TODO: временное решение, не решено, что лучше:
# поискать по базе или сразу подтянуть с сайта
def make_shikimori_similar_tool():

    @tool
    def shikimori_similar(anime_id: str) -> str:
        """
        Получает список похожих аниме с Shikimori.one по id аниме.
        Используй когда пользователь просит найти похожее на конкретное аниме.
        Передавай числовой id аниме из результатов sql_search.
        Если результатов мало (меньше 3) — используй qdrant_search для поиска по атмосфере.
        """
        try:
            items = _fetch_similar(anime_id)
        except Exception as e:
            return f"Не удалось получить похожие аниме: {e}"

        if not items:
            return "SIMILAR_EMPTY: Shikimori не нашёл похожих аниме. Используй qdrant_search."

        if len(items) < 3:
            header = f"Shikimori нашёл мало похожих (только {len(items)}). Дополни через qdrant_search:\n"
        else:
            header = "Похожие аниме по версии Shikimori:\n"

        return f"{header}{_format(items)}"

    return shikimori_similar

# C данной функцией пока будем без тулы для новостей.
def make_shikimori_tool():

    @tool
    def shikimori_search(query: str) -> str:
        """
        Получает актуальные данные с Shikimori.one в реальном времени.
        Используй когда пользователь спрашивает:
        - онгоинги ('что сейчас идёт', 'текущий сезон', 'онгоинги')
        - анонсы ('что скоро выйдет', 'анонсы', 'ожидаемые аниме')
        - топ по сезону или году ('лучшее аниме осени 2024', 'топ аниме 2023', 'топ зимы 2025')
        НЕ используй для поиска по описанию или атмосфере — для этого есть qdrant_search.
        """
        q = query.lower()

        # Топ по сезону/году
        season = _parse_season(q)
        if season or any(w in q for w in ["топ", "лучш", "рейтинг"]):
            params = {"season": season} if season else {}
            items = _fetch_animes(params, limit=10)
            header = f"Топ аниме{' сезона ' + season if season else ''}:"
            if not items:
                return "Не удалось получить данные с Shikimori."
            return f"{header}\n{_format(items)}"

        # Анонсы
        if any(w in q for w in ["анонс", "скоро", "ожидаем", "выйдет", "будущ"]):
            items = _fetch_animes({"status": "anons"}, limit=10)
            header = "Анонсированные аниме (скоро выйдут):"
            if not items:
                return "Не удалось получить данные с Shikimori."
            return f"{header}\n{_format(items)}"

        # Онгоинги (по умолчанию )
        items = _fetch_animes({"status": "ongoing"}, limit=10)
        header = "Текущие онгоинги:"
        if not items:
            return "Не удалось получить данные с Shikimori."
        return f"{header}\n{_format(items)}"

    return shikimori_search
