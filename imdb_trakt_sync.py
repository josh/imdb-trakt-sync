import csv
import json
import logging
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from time import sleep
from typing import Any, Literal, TypedDict

import click
import requests

logger = logging.getLogger("imdb-trakt-sync")

last_request: datetime = datetime(1970, 1, 1)
_MIN_TIME_BETWEEN_REQUESTS = timedelta(seconds=3)

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
@click.pass_obj
def sync_watchlist(session: requests.Session, imdb_watchlist_url: str) -> None:
    items = fetch_imdb_watchlist(imdb_watchlist_url)

    existing_media_items = trakt_watchlist(session)
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

    trakt_update_watchlist(session, movies=add_movies, shows=add_shows)
    trakt_remove_from_watchlist(session, movies=remove_movies, shows=remove_shows)


@main.command()
@click.option(
    "--imdb-ratings-url",
    required=True,
    envvar="IMDB_RATINGS_URL",
)
@click.pass_obj
def sync_ratings(session: requests.Session, imdb_ratings_url: str) -> None:
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

    trakt_add_ratings(session=session, movies=add_movies, shows=add_shows)


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


class TraktRatedItem(TypedDict):
    rated_at: str
    rating: int
    ids: TraktIMDBIDs


class TraktRatingItem(TypedDict):
    rated_at: str
    rating: int
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
_TRAKT_ADD_RATINGS_URL = "https://api.trakt.tv/sync/ratings"
_TRAKT_REMOVE_RATINGS_URL = "https://api.trakt.tv/sync/ratings/remove"


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
    global last_request
    now = datetime.now()
    wait = last_request + _MIN_TIME_BETWEEN_REQUESTS - now
    if wait.total_seconds() > 0:
        logger.debug("Sleeping for %s", wait)
        sleep(wait.total_seconds())
    last_request = now
    response = session.request(method, url, **kwargs)
    response.raise_for_status()

    ratelimit: TraktRatelimit = json.loads(response.headers["x-ratelimit"])
    if ratelimit["remaining"] < ratelimit["limit"] * 0.25:
        logger.warning("Rate limit < 25%% remaining: %s", ratelimit)
        sleep(10)
    elif ratelimit["remaining"] < ratelimit["limit"] * 0.10:
        logger.error("Rate limit < 10%% remaining: %s", ratelimit)
        sleep(60)

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


def trakt_ratings(
    session: requests.Session,
    media_type: Literal["movies", "shows", "seasons", "episodes", "all"] = "all",
) -> list[TraktRatingItem]:
    response = trakt_request(
        session,
        method="GET",
        url=f"{_TRAKT_RATINGS_URL}/{media_type}",
    )
    data: list[TraktRatingItem] = response.json()
    return data


def trakt_add_ratings(
    session: requests.Session,
    movies: list[TraktRatedItem] = [],
    shows: list[TraktRatedItem] = [],
    seasons: list[TraktRatedItem] = [],
    episodes: list[TraktRatedItem] = [],
) -> None:
    if not movies and not shows and not seasons and not episodes:
        logger.debug("No items to rate")
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


class TraktTypedContainer(TypedDict):
    type: Literal["movie", "show", "season", "episode"]
    movie: TraktAnyItem
    show: TraktAnyItem
    season: TraktAnyItem
    episode: TraktAnyItem


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


if __name__ == "__main__":
    main()
