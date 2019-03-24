#!/bin/bash
# Usage: sync

usage() {
  sed -ne '/^#/!q;s/.\{1,2\}//;1d;p' < "$0"
  exit 1
}

[ -n "$IMDB_ID" ] || usage
[ -n "$IMDB_SID" ] || usage
[ -n "$IMDB_RATINGS_ID" ] || usage
[ -n "$IMDB_WATCHLIST_ID" ] || usage
[ -n "$TRAKT_ACCESS_TOKEN" ] || usage
[ -n "$TRAKT_CLIENT_ID" ] || usage

set -euxo pipefail

./imdb-watchlist.sh "$IMDB_WATCHLIST_ID" > imdb-watchlist.json
./trakt-watchlist.sh "$TRAKT_CLIENT_ID" "$TRAKT_ACCESS_TOKEN" > trakt-watchlist.json
node ./index.js watchlist imdb-watchlist.json trakt-watchlist.json
rm imdb-watchlist.json trakt-watchlist.json

./imdb-ratings.sh "$IMDB_RATINGS_ID" "$IMDB_ID" "$IMDB_SID" > imdb-ratings.json
./trakt-ratings.sh "$TRAKT_CLIENT_ID" "$TRAKT_ACCESS_TOKEN" > trakt-ratings.json
node ./index.js ratings imdb-ratings.json trakt-ratings.json
rm imdb-ratings.json trakt-ratings.json
