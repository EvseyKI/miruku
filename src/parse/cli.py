import argparse
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from parse.client import GraphQLClient
from parse.logger import create_logger
import parse.pipeline as pipeline


def parse_args() -> argparse.Namespace:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Парсер аниме с Shikimori.")

    parser.add_argument(
        "--client_id",
        type=str,
        default=os.getenv("SHIKI_CLIENT_ID"),
        help="Client ID приложения Shikimori.",
    )
    parser.add_argument(
        "--client_secret",
        type=str,
        default=os.getenv("SHIKI_CLIENT_SECRET"),
        help="Client Secret приложения Shikimori.",
    )
    parser.add_argument(
        "--auth_code",
        default=os.getenv("SHIKI_AUTH_CODE"),
        help="Код авторизации для получения access token.",
    )
    parser.add_argument(
        "--access_token",
        type=str,
        default=os.getenv("SHIKI_ACCESS_TOKEN"),
        help="Access token (если уже есть).",
    )
    parser.add_argument(
        "--refresh_token",
        type=str,
        default=os.getenv("SHIKI_REFRESH_TOKEN"),
        help="Refresh token для обновления access token.",
    )
    parser.add_argument(
        "--endpoint",
        type=str,
        default=os.getenv("SHIKI_BASE_HOST"),
        help="URL GraphQL эндпоинта Shikimori.",
    )
    parser.add_argument(
        "--refresh_if_expired",
        action="store_true",
        help="Обновить access token перед запуском.",
    )
    parser.add_argument(
        "--output",
        default=Path(__file__).resolve().parents[2] / "output",
        type=Path,
        help="Путь для сохранения результатов.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=1,
        help="Максимальное количество страниц GraphQL (по 50 аниме). По умолчанию: 1.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=1.0,
        help="Задержка между запросами в секундах.",
    )
    parser.add_argument(
        "--checkpoint-every",
        type=int,
        default=500,
        help="Сохранять чекпоинт каждые N аниме. По умолчанию: 500.",
    )
    parser.add_argument(
        "--count",
        action="store_true",
        help="Вывести общее количество аниме на Shikimori и выйти.",
    )

    return parser.parse_args()


def _init_graphql_client(logger: logging.Logger, args: argparse.Namespace) -> GraphQLClient:
    client = GraphQLClient(url=args.endpoint, client_id=args.client_id, client_secret=args.client_secret, timeout=args.timeout)
    access_token = args.access_token

    if not access_token:
        if not args.auth_code:
            raise ValueError("auth_code or access_token is required")
        logger.info("Fetching access token...")
        access_token = client.get_access_token(args.auth_code).json().get("access_token")

    elif args.refresh_if_expired:
        logger.info("Refreshing access token...")
        access_token = client.refresh_access_token(args.refresh_token).json().get("access_token")

    if not access_token:
        raise ValueError("Failed to obtain access token")

    client.init(access_token)
    logger.info("GraphQL client initialized")
    return client


def main():
    logger = create_logger()
    args = parse_args()

    if args.count:
        client = GraphQLClient(url=args.endpoint, client_id=args.client_id, client_secret=args.client_secret, timeout=args.timeout)
        print(f"Total anime on Shikimori: {client.get_anime_count()}")
        return

    graphql_client = _init_graphql_client(logger, args)

    anime_gql = Path(__file__).resolve().parent / "anime.gql"
    query = anime_gql.read_text(encoding="utf-8")

    pipeline.run(
        graphql_client=graphql_client,
        query=query,
        output_path=args.output,
        max_pages=args.max_pages,
        checkpoint_every=args.checkpoint_every,
    )


if __name__ == "__main__":
    main()
