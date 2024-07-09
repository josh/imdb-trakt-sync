import csv
import logging
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path
from time import sleep
from typing import Any, Literal, TypedDict

import click
import requests

logger = logging.getLogger("imdb-trakt-sync")

last_request: datetime = datetime(1970, 1, 1)
_MIN_TIME_BETWEEN_REQUESTS = timedelta(seconds=3)

_IMDB_MOVIE_TYPES: set[str] = {"Movie", "Short"}
_IMDB_SHOW_TYPES: set[str] = {"TV Series", "TV Mini Series"}
_IMDB_TYPES: set[str] = _IMDB_MOVIE_TYPES | _IMDB_SHOW_TYPES


@click.group()
@click.option(
    "--trakt-client-id",
    required=True,
    envvar="TRAKT_CLIENT_ID",
)
@click.option(
    "--trakt-access-token",
    required=True,
    envvar="TRAKT_ACCESS_TOKEN",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose logging",
    envvar="ACTIONS_RUNNER_DEBUG",
)
@click.pass_context
def main(
    ctx: click.Context,
    trakt_client_id: str,
    trakt_access_token: str,
    verbose: bool,
) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO)
    ctx.obj = trakt_session(trakt_client_id, trakt_access_token)


@main.command()
@click.option(
    "--imdb-watchlist-url",
    required=True,
    envvar="IMDB_WATCHLIST_URL",
)
@click.pass_obj
def sync_watchlist(session: requests.Session, imdb_watchlist_url: str) -> None:
    lines = _iterlines(imdb_watchlist_url)
    rows = [row for row in csv.DictReader(lines)]

    for row in rows:
        if row["Title Type"] not in _IMDB_TYPES:
            logger.warning("Unknown title type: %s %s", row["Title Type"], row["Const"])

    existing_media_items = trakt_watchlist(session)
    existing_movie_imdb_ids: set[str] = {
        item["movie"]["ids"]["imdb"]
        for item in existing_media_items
        if item.get("movie", {}).get("ids", {}).get("imdb")
    }
    existing_show_imdb_ids: set[str] = {
        item["show"]["ids"]["imdb"]
        for item in existing_media_items
        if item.get("show", {}).get("ids", {}).get("imdb")
    }

    imdb_movie_ids: set[str] = {
        row["Const"] for row in rows if row["Title Type"] in _IMDB_MOVIE_TYPES
    }
    imdb_show_ids: set[str] = {
        row["Const"] for row in rows if row["Title Type"] in _IMDB_SHOW_TYPES
    }

    add_movies: list[TraktAnyItem] = [
        {"ids": {"imdb": imdb}} for imdb in imdb_movie_ids - existing_movie_imdb_ids
    ]
    add_shows: list[TraktAnyItem] = [
        {"ids": {"imdb": imdb}} for imdb in imdb_show_ids - existing_show_imdb_ids
    ]
    remove_movies: list[TraktAnyItem] = [
        {"ids": {"imdb": imdb}} for imdb in existing_movie_imdb_ids - imdb_movie_ids
    ]
    remove_shows: list[TraktAnyItem] = [
        {"ids": {"imdb": imdb}} for imdb in existing_show_imdb_ids - imdb_show_ids
    ]

    trakt_update_watchlist(session, movies=add_movies, shows=add_shows)
    trakt_remove_from_watchlist(session, movies=remove_movies, shows=remove_shows)


class TraktIMDBIDs(TypedDict):
    imdb: str


class TraktAnyItem(TypedDict):
    ids: TraktIMDBIDs


class TraktWatchlistItem(TypedDict):
    rank: int
    id: int
    type: Literal["movie", "show", "season", "episode"]
    movie: TraktAnyItem
    show: TraktAnyItem
    season: TraktAnyItem
    episode: TraktAnyItem


_TRAKT_API_HEADERS = {
    "Content-Type": "application/json",
    "trakt-api-key": "",
    "trakt-api-version": "2",
    "Authorization": "Bearer [access_token]",
}
_TRAKT_WATCHLIST_URL = "https://api.trakt.tv/sync/watchlist"
_TRAKT_UPDATE_WATCHLIST_URL = "https://api.trakt.tv/sync/watchlist"
_TRAKT_REMOVE_FROM_WATCHLIST_URL = "https://api.trakt.tv/sync/watchlist/remove"


def trakt_session(client_id: str, access_token: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(_TRAKT_API_HEADERS)
    session.headers["trakt-api-key"] = client_id
    session.headers["Authorization"] = f"Bearer {access_token}"
    return session


def trakt_request(
    session: requests.Session,
    method: Literal["GET", "POST", "PUT", "DELETE"],
    url: str,
    **kwargs: Any,
) -> requests.Response:
    global last_request
    now = datetime.now()
    wait = last_request + _MIN_TIME_BETWEEN_REQUESTS - now
    if wait.total_seconds() > 0:
        logger.debug("Sleeping for %s", wait)
        sleep(wait.total_seconds())
    last_request = now
    response = session.request(method, url, **kwargs)
    response.raise_for_status()
    return response


def trakt_watchlist(session: requests.Session) -> list[TraktWatchlistItem]:
    response = trakt_request(session, method="GET", url=_TRAKT_WATCHLIST_URL)
    data: list[TraktWatchlistItem] = response.json()
    return data


def trakt_update_watchlist(
    session: requests.Session,
    movies: list[TraktAnyItem] = [],
    shows: list[TraktAnyItem] = [],
    seasons: list[TraktAnyItem] = [],
    episodes: list[TraktAnyItem] = [],
) -> None:
    if not movies and not shows and not seasons and not episodes:
        logger.debug("No items to update")
        return

    data = {
        "movies": movies,
        "shows": shows,
        "seasons": seasons,
        "episodes": episodes,
    }
    response = trakt_request(
        session,
        method="POST",
        url=_TRAKT_UPDATE_WATCHLIST_URL,
        json=data,
    )
    result = response.json()

    for media_type in ["movies", "shows", "seasons", "episodes"]:
        added: int = result["added"][media_type]
        existing: int = result["existing"][media_type]
        not_found: list[TraktAnyItem] = result["not_found"][media_type]
        if added > 0:
            logger.info("Added %d %s to watchlist", added, media_type)
        if existing > 0:
            logger.debug("%d %s already in watchlist", existing, media_type)
        if not_found:
            for item in not_found:
                logger.warning(
                    "https://www.imdb.com/title/%s/ not found on Trakt",
                    item["ids"]["imdb"],
                )


def trakt_remove_from_watchlist(
    session: requests.Session,
    movies: list[TraktAnyItem] = [],
    shows: list[TraktAnyItem] = [],
    seasons: list[TraktAnyItem] = [],
    episodes: list[TraktAnyItem] = [],
) -> None:
    if not movies and not shows and not seasons and not episodes:
        logger.debug("No items to remove")
        return

    data = {
        "movies": movies,
        "shows": shows,
        "seasons": seasons,
        "episodes": episodes,
    }
    response = trakt_request(
        session, method="POST", url=_TRAKT_REMOVE_FROM_WATCHLIST_URL, json=data
    )
    result = response.json()
    for media_type in ["movies", "shows", "seasons", "episodes"]:
        deleted: int = result["deleted"][media_type]
        not_found: list[TraktAnyItem] = result["not_found"][media_type]
        if deleted > 0:
            logger.info("Deleted %d %s from watchlist", deleted, media_type)
        if not_found:
            for item in not_found:
                logger.warning(
                    "https://www.imdb.com/title/%s/ not found on Trakt",
                    item["ids"]["imdb"],
                )


def _iterlines(path: Path | str) -> Iterator[str]:
    if isinstance(path, str) and path.startswith("http"):
        logger.debug("Fetching remote '%s'", path)
        response = requests.get(path)
        response.raise_for_status()
        yield from response.iter_lines(decode_unicode=True)
    else:
        logger.debug("Reading local file '%s'", path)
        with open(path) as f:
            yield from f


if __name__ == "__main__":
    main()
