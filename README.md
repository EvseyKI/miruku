# Miruku

<p align="center">
  <a href="https://python.org"><img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white"/></a>
  <a href="https://python.langchain.com"><img src="https://img.shields.io/badge/LangChain-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white"/></a>
  <a href="https://qdrant.tech"><img src="https://img.shields.io/badge/Qdrant-DC244C?style=for-the-badge&logo=qdrant&logoColor=white"/></a>
  <a href="https://streamlit.io"><img src="https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white"/></a>
  <a href="https://pypi.org/project/gql/"><img src="https://img.shields.io/badge/gql-3A3A3A?style=for-the-badge&logo=graphql&logoColor=E10098"/></a>
  <a href="https://sqlite.org"><img src="https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white"/></a>
  <a href="https://python-poetry.org"><img src="https://img.shields.io/badge/Poetry-60A5FA?style=for-the-badge&logo=poetry&logoColor=white"/></a>
</p>

---

Miruku — это AI-агент для поиска и рекомендации аниме. Он понимает запросы на естественном языке («что-нибудь мрачное про самураев с хорошим рейтингом»), умеет находить похожее по атмосфере и пожеланиям, отслеживать онгоинги в реальном времени и даже находить аниме-аналоги по описанию любого фильма или игры.

Доступен в двух интерфейсах: **Streamlit-приложение** и **Telegram-бот**.

---

## Возможности

- **Семантический поиск** — поиск по описанию через векторную БД Qdrant с фильтрацией по метаданным и LLM-переранжированием результатов
- **Структурированный поиск** — топ-листы, фильтры по жанру, студии, году, рейтингу через SQLite
- **Актуальные данные** — онгоинги, анонсы и сезонные топы в реальном времени с Shikimori API
- **Похожие тайтлы** — поиск похожих аниме по id через Shikimori + fallback на векторный поиск
- **Кроссмедийный поиск** — агент гуглит описание любого фильма, сериала или игры через DuckDuckGo и находит аниме с похожим сюжетом
- **Память диалога** — агент помнит контекст последних 6 рекомендаций в сессии
- **Медиа-превью** — постер, ссылка на Shikimori и трейлер прямо в чате
- **Стриминг ответов** — потоковый вывод токенов в Streamlit-интерфейсе

---

## Инструменты агента

| Инструмент | Описание | Когда используется |
|---|---|---|
| `qdrant_search` | Семантический поиск по векторной БД с pre-фильтрацией | Поиск по атмосфере, сюжету, ощущению |
| `sql_search` | SQL-агент поверх SQLite через LangChain | Топ-листы, конкретные студии, франшизы, рейтинги |
| `shikimori_search` | Актуальные данные с Shikimori REST API | Онгоинги, анонсы, топ по сезону/году |
| `shikimori_similar` | Список похожих аниме по id с Shikimori | «Найди похожее на ...» по конкретному тайтлу |
| `web_search` | Поиск в интернете через DuckDuckGo | Когда упоминается не-аниме произведение |

---

## Установка зависимостей

### Требования
- Python 3.12+
- Conda
- Docker (для Qdrant)

### 1. Создать conda-окружение

```bash
conda create -y -n shiki_env python=3.12
conda activate shiki_env
```

### 2. Установить зависимости

```bash
pip install -r requirements.txt
```

---

## Переменные окружения

Скопируй `.env.example` в `.env` и заполни:

```bash
cp .env.example .env
```

```env
# GraphQL endpoint Shikimori
SHIKI_BASE_HOST=https://shikimori.one

# OAuth токены (нужны для парсера, см. раздел ниже)
SHIKI_CLIENT_ID=your_client_id_here
SHIKI_CLIENT_SECRET=your_client_secret_here
SHIKI_AUTH_CODE=your_auth_code_here
SHIKI_ACCESS_TOKEN=your_access_token_here
SHIKI_REFRESH_TOKEN=your_refresh_token_here

# Telegram-бот
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# LLM-провайдер vsellm (OpenAI-совместимый API)
VSELLM_API_KEY=your_api_key_here
VSELLM_BASE_URL=https://api.vsellm.ru/v1

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333
```

---

## Парсинг данных с Shikimori

### Получение OAuth-токенов

Данные спарсены с [shikimori.io](https://shikimori.io/). Для получения токенов следуй инструкции: [shikimori.io/oauth](https://shikimori.io/oauth)

### Запуск парсера

```bash
# Узнать общее количество аниме на Shikimori
python -m parse.cli --count

# Спарсить первые 50 аниме (1 страница)
python -m parse.cli --max-pages 1
```

Результат сохраняется в `output/anime_full.json`. Парсер поддерживает **чекпоинты** — при прерывании продолжит с последней сохранённой позиции.

> **Параметры CLI:**
> - `--max-pages` — количество страниц GraphQL (50 аниме/стр.), по умолчанию `1`
> - `--timeout` — задержка между запросами в секундах, по умолчанию `1.0`
> - `--checkpoint-every` — сохранять чекпоинт каждые N аниме, по умолчанию `500`
> - `--output` — путь для сохранения результатов

---

## 🧹 Очистка данных и векторизация

Очищенный датасет уже загружен на HuggingFace:  
[EvseyKI/shikimori-clean-v1](https://huggingface.co/datasets/EvseyKI/shikimori-clean-v1)

Для самостоятельной обработки — открой ноутбук:

```bash
jupyter notebook notebooks/test_nlp.ipynb
```

Ноутбук выполняет следующие шаги:

1. **Нормализация** — очистка сырых JSON-данных: нормализация полей, удаление дублей, фильтрация по качеству (готовый файл по ссылке выше)
2. **Формирование SQLite БД** — создание `data/anime.db` со схемой: `anime`, `genre`, `theme`, `demographic`, `studio` и junction-таблицами
3. **Векторизация** — генерация эмбеддингов через `google/gemini-embedding-001` (via vsellm)
4. **Загрузка в Qdrant** — создание коллекции `anime_storage` с payload-фильтрами по жанрам, темам, рейтингу, году

После выполнения ноутбука в `data/` появится `anime.db`, а Qdrant-коллекция будет готова к поиску.

---

## Запуск Qdrant

Перед запуском проекта необходимо поднять Qdrant:

```bash
docker run -d \
  --name qdrant \
  -p 6333:6333 \
  -v $(pwd)/qdrant_storage:/qdrant/storage \
  qdrant/qdrant
```

Qdrant будет доступен на `http://localhost:6333`.  

> Данные коллекции сохраняются в `qdrant_storage/` — том монтируется при каждом запуске контейнера.

---

## Запуск проекта

Убедись, что:
- Qdrant запущен (`docker ps` или `http://localhost:6333/dashboard`)
- Заполнен `.env`
- Выполнен ноутбук (`data/anime.db` и Qdrant-коллекция созданы)

### Streamlit-приложение

```bash
streamlit run src/app.py
```

Откроется в браузере по адресу `http://localhost:8501`

### Telegram-бот

```bash
python src/bot.py
```

Бот хранит историю диалогов каждого пользователя в `data/histories.db` (SQLite).
