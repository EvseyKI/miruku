import json
import logging
from typing import Literal

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pydantic import BaseModel, model_validator
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny, Range

from model.prompt import PROMPT_EXTRACT_FILTERS


GenreType = Literal[
    "Авангард", "Гурман", "Драма", "Комедия", "Повседневность",
    "Приключения", "Романтика", "Сверхъестественное", "Спорт",
    "Тайна", "Триллер", "Ужасы", "Фантастика", "Фэнтези", "Экшен"
]

ThemeType = Literal[
    "Городское фэнтези", "Злодейка", "CGDCT", "Антропоморфизм",
    "Боевые искусства", "Вампиры", "Взрослые персонажи", "Видеоигры",
    "Военное", "Выживание", "Гарем", "Гонки", "Гэг-юмор", "Детектив",
    "Жестокость", "Забота о детях", "Игра с высокими ставками",
    "Идолы (Жен.)", "Идолы (Муж.)", "Изобразительное искусство",
    "Исполнительское искусство", "Исторический", "Исэкай", "Иясикэй",
    "Командный спорт", "Космос", "Кроссдрессинг", "Культура отаку",
    "Любовный многоугольник", "Магическая смена пола", "Махо-сёдзё",
    "Медицина", "Меха", "Мифология", "Музыка", "Образовательное",
    "Организованная преступность", "Пародия", "Питомцы", "Психологическое",
    "Путешествие во времени", "Работа", "Реверс-гарем", "Реинкарнация",
    "Романтический подтекст", "Самураи", "Спортивные единоборства",
    "Стратегические игры", "Супер сила", "Удостоено наград",
    "Хулиганы", "Школа", "Шоу-бизнес"
]


class RerankResult(BaseModel):
    id: int


class AnimeFilters(BaseModel):
    genres_include: list[GenreType] | None = None
    themes_include: list[ThemeType] | None = None

    genres_exclude: list[GenreType] | None = None
    themes_exclude: list[ThemeType] | None = None

    score_min: float | None = None
    score_max: float | None = None
    year_min: int | None = None
    year_max: int | None = None
    episodes_min: int | None = None
    episodes_max: int | None = None
    duration_min: int | None = None
    duration_max: int | None = None

    @model_validator(mode="before")
    @classmethod
    def drop_unknown(cls, values):
        known = cls.model_fields.keys()
        return {k: v for k, v in values.items() if k in known}


def build_qdrant_filter(filters: AnimeFilters) -> Filter:
    must = []
    must_not = [
        FieldCondition(key="rating", match=MatchAny(any=["rx", "r_plus"])),
    ]

    if filters.genres_include:
        must.append(
            FieldCondition(key="genres", match=MatchAny(any=filters.genres_include))
        )

    if filters.themes_include:
        must.append(
            FieldCondition(key="themes", match=MatchAny(any=filters.themes_include))
        )

    for genre in (filters.genres_exclude or []):
        must_not.append(
            FieldCondition(key="genres", match=MatchValue(value=genre))
        )

    for theme in (filters.themes_exclude or []):
        must_not.append(
            FieldCondition(key="themes", match=MatchValue(value=theme))
        )

    range_fields = {
        "score":    ("score_min",    "score_max"),
        "year":     ("year_min",     "year_max"),
        "episodes": ("episodes_min", "episodes_max"),
        "duration": ("duration_min", "duration_max"),
    }
    for field, (fmin, fmax) in range_fields.items():
        lo = getattr(filters, fmin)
        hi = getattr(filters, fmax)
        if lo is not None or hi is not None:
            must.append(
                FieldCondition(key=field, range=Range(gte=lo, lte=hi))
            )

    return Filter(
        must=must if must else None,
        must_not=must_not if must_not else None,
    )


class VectorDBSearch:
    def __init__(
        self,
        llm: ChatOpenAI,
        embeddings: OpenAIEmbeddings,
        qdrant_client: QdrantClient,
        collection_name: str,
        top_k: int = 5,
    ):
        self._llm = llm.with_structured_output(AnimeFilters)
        self._reranker = llm.with_structured_output(RerankResult)
        self._embeddings = embeddings
        self._client = qdrant_client
        self._collection = collection_name
        self._top_k = top_k

    def search(self, query: str, history: list[str] | None = None) -> list[dict]:
        """
        1. LLM извлекает фильтры из запроса -> AnimeFilters.
        2. Embedding векторизует запрос.
        3. Qdrant ищет top_k кандидатов с pre-filter.
        4. LLM-реранкер выбирает лучшего кандидата.
        Возвращает список из одного payload-словаря.
        """
        filters = self._extract_filters(query)
        qdrant_filter = build_qdrant_filter(filters)
        vector = self._embeddings.embed_query(query)

        points = self._client.query_points(
            collection_name=self._collection,
            query=vector,
            query_filter=qdrant_filter,
            limit=self._top_k,
        ).points

        candidates = [{"id": r.id, **r.payload} for r in points]
        if not candidates:
            return []

        best = self._rerank(query, candidates, history=history)
        return [best]

    def _rerank(self, query: str, candidates: list[dict], history: list[str] | None = None) -> dict:
        candidates_text = "\n\n".join(
            f"id={c['id']} | {c.get('russian', '')} | "
            f"Жанры: {', '.join(c.get('genres') or [])} | "
            f"Темы: {', '.join(c.get('themes') or [])} | "
            f"Описание: {str(c.get('description', ''))[:300]}"
            for c in candidates
        )
        history_text = ""
        if history:
            history_text = "История диалога:\n" + "\n".join(f"- {h}" for h in history) + "\n\n"
        prompt = (
            f"{history_text}"
            f"Текущий запрос пользователя: {query}\n\n"
            f"Кандидаты:\n{candidates_text}\n\n"
            "Выбери id одного аниме, которое лучше всего соответствует запросу "
            "с учётом всего контекста диалога."
        )
        try:
            result = self._reranker.invoke(prompt)
            match = next((c for c in candidates if c["id"] == result.id), None)
            return match or candidates[0]
        except Exception:
            return candidates[0]

    def _extract_filters(self, query: str) -> AnimeFilters:
        messages = PROMPT_EXTRACT_FILTERS.format_messages(query=query)
        try:
            return self._llm.invoke(messages)
        except Exception:
            return AnimeFilters()
