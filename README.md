# IMDb Trakt Sync

Script to sync [IMDb](https://www.imdb.com) ratings and watchlist to [Trakt.tv](https://trakt.tv).

**docker-compose.yml**

```yaml
version: "3"
services:
  imdb_trakt_sync:
    restart: always
    image: ghcr.io/josh/imdb-trakt-sync
    environment:
      - IMDB_UBID_MAIN=***
      - IMDB_AT_MAIN=***
      - IMDB_RATINGS_ID=ur***
      - IMDB_WATCHLIST_ID=ls***
      - TRAKT_CLIENT_ID=
      - TRAKT_ACCESS_TOKEN=
      - TICKERD_INTERVAL=1h
```

## Environment Variables

Log into [imdb.com](https://www.imdb.com) and use the web inspector to extract the following cookies:

- `IMDB_UBID_MAIN`: `ubid-main`
- `IMDB_AT_MAIN`: `at-main`

<img width="200" alt="Screen Shot 2020-09-03 at 10 31 26 AM" src="https://user-images.githubusercontent.com/137/92148025-c8703a00-edd0-11ea-84a7-58b402c4aa14.png">

Click "Watchlist" and see the URL bar for `https://www.imdb.com/user/ur***/watchlist`, then Edit for `https://www.imdb.com/list/ls**/edit`

- `IMDB_RATINGS_ID`: The ID that starts with `ur`
- `IMDB_WATCHLIST_ID`: The ID that starts with `ls`

Create a [Trakt API App](https://trakt.tv/oauth/applications):

- `TRAKT_CLIENT_ID`: Trakt Client ID
- `TRAKT_ACCESS_TOKEN`: "Authorize" the OAuth token to get a personal access token

Set a sync interval:

- `TICKERD_INTERVAL`: `1h`
