import json
from pathlib import Path

from parse.client import GraphQLClient
from parse.logger import create_logger

_logger = create_logger(component="pipeline")


def run(
    graphql_client: GraphQLClient,
    query: str,
    output_path: Path,
    max_pages: int = 200,
    checkpoint_every: int = 500,
) -> None:
    """
    Full pipeline: GraphQL fetch -> save.

    Parameters
    ----------
    graphql_client : GraphQLClient
        Initialized GraphQL client.
    query : str
        GraphQL query string (should include pagination via $page variable).
    output_path : Path
        Directory where output files will be written.
    max_pages : int
        Max number of GraphQL pages to fetch (50 anime per page).
    checkpoint_every : int
        Save a checkpoint every N anime processed.
    """
    output_path.mkdir(parents=True, exist_ok=True)
    checkpoint_file = output_path / "anime_full_checkpoint.json"
    final_file = output_path / "anime_full.json"

    # Resume from checkpoint if exists
    processed = []
    seen_ids = set()
    if checkpoint_file.exists():
        _logger.info(f"Resuming from checkpoint: {checkpoint_file}")
        with checkpoint_file.open(encoding="utf-8") as f:
            processed = json.load(f)
        seen_ids = {str(a["id"]) for a in processed}
        _logger.info(f"Loaded {len(processed)} anime from checkpoint")

    _logger.info("Fetching anime via GraphQL...")
    all_anime = graphql_client.execute(query, max_pages=max_pages)
    _logger.info(f"Fetched {len(all_anime)} anime total")

    new_anime = [a for a in all_anime if str(a["id"]) not in seen_ids]
    _logger.info(f"{len(new_anime)} new anime to process")

    for i, anime in enumerate(new_anime, start=1):
        anime["characterRoles"] = [
            r for r in anime.get("characterRoles", []) if "Main" in r.get("rolesEn", [])
        ]
        anime["personRoles"] = anime.get("personRoles", [])[:5]
        videos = anime.get("videos", [])
        pv = next((v for v in videos if v.get("kind") == "pv"), None)
        anime["videos"] = [pv] if pv else videos[:1]

        processed.append(anime)

        if i % checkpoint_every == 0:
            _save_json(checkpoint_file, processed)
            _logger.info(f"Checkpoint saved ({len(processed)} anime)")

    _save_json(final_file, processed)
    _logger.info(f"Done. Saved {len(processed)} anime to {final_file}")

    if checkpoint_file.exists():
        checkpoint_file.unlink()
        _logger.info("Checkpoint file removed")


def _save_json(path: Path, data: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
