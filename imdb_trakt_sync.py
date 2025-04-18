import csv
import logging
import os
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from time import sleep
from typing import Any, Literal, TypedDict, TypeVar, cast

import click
import requests

logger = logging.getLogger("imdb-trakt-sync")

_NOW: datetime = datetime.now()
_END_OF_DAY_TIME: time = time(hour=23, minute=59, second=59)

_IMDB_MOVIE_TYPES: set[str] = {"Movie", "Short", "TV Movie", "TV Special", "Video"}
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
@click.option(
    "--dry-run",
    is_flag=True,
    help="Enable dry run mode",
)
@click.pass_obj
def sync_watchlist(
    session: requests.Session,
    imdb_watchlist_url: str,
    dry_run: bool,
) -> None:
    items = fetch_imdb_watchlist(imdb_watchlist_url)

    existing_media_items = list(trakt_watchlist(session))
    existing_movie_imdb_ids: set[str] = _compact_set(
        _trakt_mediaitem_imdb_id(item)
        for item in existing_media_items
        if item["type"] == "movie"
    )
    existing_show_imdb_ids: set[str] = _compact_set(
        _trakt_mediaitem_imdb_id(item)
        for item in existing_media_items
        if item["type"] == "show"
    )

    imdb_movie_ids: set[str] = {
        item.imdb_id for item in items if item.trakt_type == "movie"
    }
    imdb_show_ids: set[str] = {
        item.imdb_id for item in items if item.trakt_type == "show"
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

    if watching_item := trakt_watching(session):
        logger.debug("Filtering out currently watching...")
        add_movies = list(_block_watching_items(add_movies, watching_item))
        add_shows = list(_block_watching_items(add_shows, watching_item))
        remove_movies = list(_block_watching_items(remove_movies, watching_item))
        remove_shows = list(_block_watching_items(remove_shows, watching_item))

    add_movies = list(_filter_unknown_imdb_ids(session, add_movies, type="movie"))
    add_shows = list(_filter_unknown_imdb_ids(session, add_shows, type="show"))

    trakt_update_watchlist(
        session,
        movies=add_movies,
        shows=add_shows,
        dry_run=dry_run,
    )
    trakt_remove_from_watchlist(
        session,
        movies=remove_movies,
        shows=remove_shows,
        dry_run=dry_run,
    )


@main.command()
@click.option(
    "--imdb-ratings-url",
    required=True,
    envvar="IMDB_RATINGS_URL",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Enable dry run mode",
)
@click.pass_obj
def sync_ratings(
    session: requests.Session,
    imdb_ratings_url: str,
    dry_run: bool,
) -> None:
    imdb_ratings = fetch_imdb_ratings(imdb_ratings_url)

    trakt_rated_at: dict[str, datetime] = {}
    trakt_rated: dict[str, int] = {}
    imdb_rated: dict[str, int] = {}

    add_movies: list[TraktRatedItem] = []
    add_shows: list[TraktRatedItem] = []

    for item in trakt_ratings(session, media_type="all"):
        if imdb_id := _trakt_mediaitem_imdb_id(item):
            trakt_rated_at[imdb_id] = _fromisoformat(item["rated_at"])
            trakt_rated[imdb_id] = item["rating"]

    for imdb_rating in imdb_ratings:
        imdb_rated[imdb_rating.imdb_id] = imdb_rating.rating

        title_rated_at = datetime.combine(imdb_rating.rated_on, _END_OF_DAY_TIME)
        title_rated_at = min(title_rated_at, _NOW)

        should_rate: bool = False

        if imdb_rating.imdb_id in trakt_rated:
            if imdb_rating.rating != trakt_rated[imdb_rating.imdb_id]:
                logger.info(
                    "Update rating https://www.imdb.com/title/%s/ %d -> %d @ %s",
                    imdb_rating.imdb_id,
                    trakt_rated[imdb_rating.imdb_id],
                    imdb_rating.rating,
                    title_rated_at,
                )
                should_rate = True

        else:
            logger.info(
                "Add rating https://www.imdb.com/title/%s/ %d @ %s",
                imdb_rating.imdb_id,
                imdb_rating.rating,
                title_rated_at,
            )
            should_rate = True

        if should_rate:
            rated_item: TraktRatedItem = {
                "rated_at": title_rated_at.isoformat(),
                "rating": imdb_rating.rating,
                "ids": {"imdb": imdb_rating.imdb_id},
            }
            if imdb_rating.trakt_type == "movie":
                add_movies.append(rated_item)
            elif imdb_rating.trakt_type == "show":
                add_shows.append(rated_item)

    not_rated_on_imdb = set(trakt_rated.keys()) - set(imdb_rated.keys())
    for imdb_id in not_rated_on_imdb:
        logger.info(
            "https://www.imdb.com/title/%s/ rated %d @ %s on Trakt, but not IMDb",
            imdb_id,
            trakt_rated[imdb_id],
            trakt_rated_at[imdb_id],
        )

    add_movies = list(_filter_unknown_imdb_ids(session, add_movies, type="movie"))
    add_shows = list(_filter_unknown_imdb_ids(session, add_shows, type="show"))

    trakt_add_ratings(
        session=session,
        movies=add_movies,
        shows=add_shows,
        dry_run=dry_run,
    )


@main.command()
@click.option(
    "--imdb-ratings-url",
    required=True,
    envvar="IMDB_RATINGS_URL",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Enable dry run mode",
)
@click.pass_obj
def sync_history(
    session: requests.Session,
    imdb_ratings_url: str,
    dry_run: bool,
) -> None:
    existing_movie_imdb_ids: set[str] = set()
    existing_episodes_imdb_ids: set[str] = set()

    imdb_id_rated_at: dict[str, date] = {}
    imdb_movie_ids: set[str] = set()
    imdb_episode_ids: set[str] = set()

    for imdb_item in fetch_imdb_ratings(imdb_ratings_url):
        imdb_id_rated_at[imdb_item.imdb_id] = imdb_item.rated_on
        if imdb_item.trakt_type == "movie":
            imdb_movie_ids.add(imdb_item.imdb_id)
        elif imdb_item.trakt_type == "episode":
            imdb_episode_ids.add(imdb_item.imdb_id)

    for trakt_item in trakt_history(session):
        if trakt_item["type"] == "movie":
            existing_movie_imdb_ids.add(trakt_item["movie"]["ids"]["imdb"])
        elif trakt_item["type"] == "episode":
            existing_episodes_imdb_ids.add(trakt_item["episode"]["ids"]["imdb"])

    add_movies: list[TraktWatchedItem] = [
        {"watched_at": imdb_id_rated_at[imdb].isoformat(), "ids": {"imdb": imdb}}
        for imdb in imdb_movie_ids - existing_movie_imdb_ids
    ]
    add_episodes: list[TraktWatchedItem] = [
        {"watched_at": imdb_id_rated_at[imdb].isoformat(), "ids": {"imdb": imdb}}
        for imdb in imdb_episode_ids - existing_episodes_imdb_ids
    ]

    if watching_item := trakt_watching(session):
        logger.debug("Filtering out currently watching...")
        add_movies = cast(
            list[TraktWatchedItem],
            list(_block_watching_items(add_movies, watching_item)),
        )
        add_episodes = cast(
            list[TraktWatchedItem],
            list(_block_watching_items(add_episodes, watching_item)),
        )

    add_movies = list(_filter_unknown_imdb_ids(session, add_movies, type="movie"))
    add_episodes = list(_filter_unknown_imdb_ids(session, add_episodes, type="episode"))

    trakt_add_history(
        session,
        movies=add_movies,
        episodes=add_episodes,
        dry_run=dry_run,
    )


@dataclass
class IMDBWatchlistItem:
    imdb_id: str
    trakt_type: Literal["movie", "show", "episode"]


@dataclass
class IMDBRatingItem:
    imdb_id: str
    rating: int
    rated_on: date
    trakt_type: Literal["movie", "show", "episode"]


def fetch_imdb_watchlist(url: str) -> list[IMDBWatchlistItem]:
    items: list[IMDBWatchlistItem] = []

    for row in csv.DictReader(_iterlines(url)):
        imdb_id = row["Const"]
        assert imdb_id.startswith("tt"), f"Invalid IMDb ID: {imdb_id}"

        trakt_type: Literal["movie", "show", "episode"] | None = None
        if row["Title Type"] in _IMDB_MOVIE_TYPES:
            trakt_type = "movie"
        elif row["Title Type"] in _IMDB_SHOW_TYPES:
            trakt_type = "show"
        assert trakt_type, f"Unknown IMDB Title Type: {row['Title Type']}"

        item = IMDBWatchlistItem(imdb_id=imdb_id, trakt_type=trakt_type)
        items.append(item)

    return items


def fetch_imdb_ratings(url: str) -> list[IMDBRatingItem]:
    items: list[IMDBRatingItem] = []

    for row in csv.DictReader(_iterlines(url)):
        imdb_id = row["Const"]
        assert imdb_id.startswith("tt"), f"Invalid IMDb ID: {imdb_id}"

        rating = int(row["Your Rating"])
        rated_on: date = datetime.strptime(row["Date Rated"], "%Y-%m-%d")

        trakt_type: Literal["movie", "show", "episode"] | None = None
        if row["Title Type"] in _IMDB_MOVIE_TYPES:
            trakt_type = "movie"
        elif row["Title Type"] in _IMDB_SHOW_TYPES:
            trakt_type = "show"
        assert trakt_type, f"Unknown IMDB Title Type: {row['Title Type']}"

        item = IMDBRatingItem(
            imdb_id=imdb_id,
            rating=rating,
            rated_on=rated_on,
            trakt_type=trakt_type,
        )
        items.append(item)

    return items


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


class TraktRatedItem(TraktAnyItem):
    rated_at: str
    rating: int


class TraktWatchingItem(TypedDict):
    expires_at: str
    started_at: str
    action: Literal["scrobble", "checkin", "watch"]
    type: Literal["movie", "episode"]
    movie: TraktAnyItem
    episode: TraktAnyItem
    show: TraktAnyItem


class TraktHistoryItem(TypedDict):
    id: int
    watched_at: str
    action: Literal["scrobble", "checkin", "watch"]
    type: Literal["movie", "episode"]
    movie: TraktAnyItem
    episode: TraktAnyItem


class TraktWatchedItem(TraktAnyItem):
    watched_at: str


class TraktRatingItem(TypedDict):
    rated_at: str
    rating: int
    type: Literal["movie", "show", "season", "episode"]
    movie: TraktAnyItem
    show: TraktAnyItem
    season: TraktAnyItem
    episode: TraktAnyItem


class TraktTypedContainer(TypedDict):
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
_TRAKT_RATINGS_URL = "https://api.trakt.tv/sync/ratings"
_TRAKT_HISTORY_URL = "https://api.trakt.tv/sync/history"
_TRAKT_ADD_RATINGS_URL = "https://api.trakt.tv/sync/ratings"
_TRAKT_REMOVE_RATINGS_URL = "https://api.trakt.tv/sync/ratings/remove"
_TRAKT_SEARCH_URL = "https://api.trakt.tv/search"


def trakt_session(client_id: str, access_token: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(_TRAKT_API_HEADERS)
    session.headers["trakt-api-key"] = client_id
    session.headers["Authorization"] = f"Bearer {access_token}"
    return session


class TraktRatelimit(TypedDict):
    name: str
    period: int
    limit: int
    remaining: int
    until: str


def trakt_request(
    session: requests.Session,
    method: Literal["GET", "POST", "PUT", "DELETE"],
    url: str,
    **kwargs: Any,
) -> requests.Response:
    response = session.request(method, url, **kwargs)
    response.raise_for_status()

    if method != "GET":
        logger.debug("Sleeping for 1 sec")
        sleep(1)

    return response


def trakt_request_paginated(
    session: requests.Session,
    method: Literal["GET"],
    url: str,
    limit: int,
) -> Iterator[Any]:
    page = 1

    while True:
        response = trakt_request(
            session,
            method=method,
            url=url,
            params={
                "page": str(page),
                "limit": str(limit),
            },
        )

        yield from response.json()

        pagination = _trakt_pagination(response)
        if pagination.page >= pagination.page_count:
            break
        page += 1


@dataclass
class TraktPagination:
    page: int
    limit: int
    page_count: int
    item_count: int


def _trakt_pagination(response: requests.Response) -> TraktPagination:
    return TraktPagination(
        page=int(response.headers["X-Pagination-Page"]),
        limit=int(response.headers["X-Pagination-Limit"]),
        page_count=int(response.headers["X-Pagination-Page-Count"]),
        item_count=int(response.headers["X-Pagination-Item-Count"]),
    )


def trakt_watchlist(session: requests.Session) -> Iterator[TraktWatchlistItem]:
    response = trakt_request(
        session,
        method="GET",
        url=_TRAKT_WATCHLIST_URL,
    )
    yield from response.json()


def trakt_update_watchlist(
    session: requests.Session,
    movies: list[TraktAnyItem] = [],
    shows: list[TraktAnyItem] = [],
    seasons: list[TraktAnyItem] = [],
    episodes: list[TraktAnyItem] = [],
    dry_run: bool = False,
) -> None:
    if not movies and not shows and not seasons and not episodes:
        logger.debug("No items to update")
        return
    if dry_run:
        if movies:
            logger.warning("[DRY RUN] Would add %d movies", len(movies))
        if shows:
            logger.warning("[DRY RUN] Would add %d shows", len(shows))
        if seasons:
            logger.warning("[DRY RUN] Would add %d seasons", len(seasons))
        if episodes:
            logger.warning("[DRY RUN] Would add %d episodes", len(episodes))
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
    dry_run: bool = False,
) -> None:
    if not movies and not shows and not seasons and not episodes:
        logger.debug("No items to remove")
        return
    if dry_run:
        if movies:
            logger.warning("[DRY RUN] Would remove %d movies", len(movies))
        if shows:
            logger.warning("[DRY RUN] Would remove %d shows", len(shows))
        if seasons:
            logger.warning("[DRY RUN] Would remove %d seasons", len(seasons))
        if episodes:
            logger.warning("[DRY RUN] Would remove %d episodes", len(episodes))
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
        url=_TRAKT_REMOVE_FROM_WATCHLIST_URL,
        json=data,
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


def trakt_watching(session: requests.Session) -> TraktWatchingItem | None:
    response = trakt_request(
        session,
        method="GET",
        url="https://api.trakt.tv/users/me/watching",
    )
    if response.status_code == 200:
        data: TraktWatchingItem = response.json()
        return data
    elif response.status_code == 204:
        return None
    else:
        response.raise_for_status()
        return None


def trakt_watching_imdb_id(session: requests.Session) -> str | None:
    if watching := trakt_watching(session):
        if watching["type"] == "movie":
            return watching["movie"]["ids"]["imdb"]
        elif watching["type"] == "episode":
            return watching["episode"]["ids"]["imdb"]
    return None


def _block_watching_items(
    items: Iterable[TraktAnyItem],
    watching: TraktWatchingItem | None,
) -> Iterator[TraktAnyItem]:
    if watching is None:
        yield from items
        return

    if watching["type"] == "movie":
        watching_imdb_id = watching["movie"]["ids"]["imdb"]
    elif watching["type"] == "episode":
        watching_imdb_id = watching["episode"]["ids"]["imdb"]
    else:
        yield from items
        return

    for item in items:
        if item["ids"].get("imdb") == watching_imdb_id:
            logger.warning(
                "https://www.imdb.com/title/%s/ is currently being watched, ignoring",
                watching_imdb_id,
            )
            continue
        else:
            yield item


T_TraktAnyItem = TypeVar("T_TraktAnyItem", bound=TraktAnyItem)


def _filter_unknown_imdb_ids(
    session: requests.Session,
    items: Iterable[T_TraktAnyItem],
    type: Literal["movie", "show", "episode"],
) -> Iterator[T_TraktAnyItem]:
    for item in items:
        imdb_id = item["ids"]["imdb"]
        response = trakt_request(
            session,
            method="GET",
            url=f"{_TRAKT_SEARCH_URL}/imdb/{imdb_id}",
            params={"type": type},
        )
        results = response.json()
        if len(results) > 0:
            logger.debug("https://www.imdb.com/title/%s/ found on Trakt", imdb_id)
            yield item
        else:
            logger.warning("https://www.imdb.com/title/%s/ not found on Trakt", imdb_id)


def trakt_ratings(
    session: requests.Session,
    media_type: Literal["movies", "shows", "seasons", "episodes", "all"] = "all",
) -> Iterator[TraktRatingItem]:
    response = trakt_request(
        session,
        method="GET",
        url=f"{_TRAKT_RATINGS_URL}/{media_type}",
    )
    yield from response.json()


def trakt_add_ratings(
    session: requests.Session,
    movies: list[TraktRatedItem] = [],
    shows: list[TraktRatedItem] = [],
    seasons: list[TraktRatedItem] = [],
    episodes: list[TraktRatedItem] = [],
    dry_run: bool = False,
) -> None:
    if not movies and not shows and not seasons and not episodes:
        logger.debug("No items to rate")
        return
    if dry_run:
        if movies:
            logger.warning("[DRY RUN] Would rate %d movies", len(movies))
        if shows:
            logger.warning("[DRY RUN] Would rate %d shows", len(shows))
        if seasons:
            logger.warning("[DRY RUN] Would rate %d seasons", len(seasons))
        if episodes:
            logger.warning("[DRY RUN] Would rate %d episodes", len(episodes))
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
        url=_TRAKT_ADD_RATINGS_URL,
        json=data,
    )
    result = response.json()

    for media_type in ["movies", "shows", "seasons", "episodes"]:
        added: int = result["added"][media_type]
        not_found: list[TraktAnyItem] = result["not_found"][media_type]
        if added > 0:
            logger.info("Added %d %s to ratings", added, media_type)
        if not_found:
            for item in not_found:
                logger.warning(
                    "https://www.imdb.com/title/%s/ not found on Trakt",
                    item["ids"]["imdb"],
                )


def trakt_remove_ratings(
    session: requests.Session,
    movies: list[TraktRatedItem] = [],
    shows: list[TraktRatedItem] = [],
    seasons: list[TraktRatedItem] = [],
    episodes: list[TraktRatedItem] = [],
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
        session,
        method="POST",
        url=_TRAKT_REMOVE_RATINGS_URL,
        json=data,
    )
    result = response.json()
    for media_type in ["movies", "shows", "seasons", "episodes"]:
        deleted: int = result["deleted"][media_type]
        not_found: list[TraktAnyItem] = result["not_found"][media_type]
        if deleted > 0:
            logger.info("Deleted %d %s from ratings", deleted, media_type)
        if not_found:
            for item in not_found:
                logger.warning(
                    "https://www.imdb.com/title/%s/ not found on Trakt",
                    item["ids"]["imdb"],
                )


def trakt_history(
    session: requests.Session,
    media_type: Literal["movies", "shows", "seasons", "episodes"] | None = None,
) -> Iterator[TraktHistoryItem]:
    url = _TRAKT_HISTORY_URL
    if media_type:
        url += f"/{media_type}"

    yield from trakt_request_paginated(
        session,
        method="GET",
        url=url,
        limit=1000,
    )


def trakt_add_history(
    session: requests.Session,
    movies: list[TraktWatchedItem] = [],
    shows: list[TraktWatchedItem] = [],
    seasons: list[TraktWatchedItem] = [],
    episodes: list[TraktWatchedItem] = [],
    dry_run: bool = False,
) -> None:
    if not movies and not shows and not seasons and not episodes:
        logger.debug("No items to add")
        return
    if dry_run:
        if movies:
            logger.warning("[DRY RUN] Would add %d movies", len(movies))
        if shows:
            logger.warning("[DRY RUN] Would add %d shows", len(shows))
        if seasons:
            logger.warning("[DRY RUN] Would add %d seasons", len(seasons))
        if episodes:
            logger.warning("[DRY RUN] Would add %d episodes", len(episodes))
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
        url=_TRAKT_HISTORY_URL,
        json=data,
    )
    result = response.json()

    for media_type in ["movies", "episodes"]:
        added: int = result["added"][media_type]
        not_found: list[TraktAnyItem] = result["not_found"][media_type]
        if added > 0:
            logger.info("Added %d %s to ratings", added, media_type)
        if not_found:
            for item in not_found:
                logger.warning(
                    "https://www.imdb.com/title/%s/ not found on Trakt",
                    item["ids"]["imdb"],
                )


def _trakt_mediaitem_imdb_id(item: TraktTypedContainer) -> str | None:
    if item["type"] == "movie":
        return item["movie"]["ids"]["imdb"]
    elif item["type"] == "show":
        return item["show"]["ids"]["imdb"]
    elif item["type"] == "season":
        return item["season"]["ids"]["imdb"]
    elif item["type"] == "episode":
        return item["episode"]["ids"]["imdb"]
    else:
        raise ValueError(f"Unknown media type: {item['type']}")


def _compact_set(s: Iterable[str | None]) -> set[str]:
    return {x for x in s if x is not None}


def _fromisoformat(s: str) -> datetime:
    assert s.endswith("Z")
    return datetime.fromisoformat(s[:-1])


class GitHubActionsFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        if record.levelno >= 40:
            levelname = "error"
        elif record.levelno >= 30:
            levelname = "warning"
        elif record.levelno >= 20:
            levelname = "notice"
        else:
            levelname = "debug"
        title = f"{record.module}.{record.funcName}"
        message = record.getMessage()
        return f"::{levelname} file={record.filename},line={record.lineno},title={title}::{message}"


if os.environ.get("GITHUB_ACTIONS") == "true":
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(GitHubActionsFormatter())
    logger.addHandler(handler)


if __name__ == "__main__":
    main()
