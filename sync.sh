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

node ./index.js watchlist <(./diff-watchlist.sh)

node ./index.js ratings <(
  node ./diff.js \
    <(./imdb-ratings.sh "$IMDB_RATINGS_ID" "$IMDB_ID" "$IMDB_SID") \
    <(./trakt-ratings.sh "$TRAKT_CLIENT_ID" "$TRAKT_ACCESS_TOKEN")
)
