#!/bin/bash
# Usage: imdb-trakt-sync

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

imdb() {
  curl --fail --silent --location \
    --cookie "id=$IMDB_ID; sid=$IMDB_SID" \
    "https://www.imdb.com$1"
}

imdb_watchlist() {
  imdb "/list/$IMDB_WATCHLIST_ID/export" | \
    ./node_modules/.bin/csvtojson | \
    jq 'map({id: .Const})'
}

imdb_ratings() {
  imdb "/user/$IMDB_RATINGS_ID/ratings/export" | \
    ./node_modules/.bin/csvtojson | \
    jq 'map({
      id: .Const,
      rating: .["Your Rating"] | tonumber,
      timestamp: .["Date Rated"] | strptime("%Y-%m-%d") | todateiso8601
    })'
}

imdb_watchlist > imdb-watchlist.json
imdb_ratings > imdb-ratings.json

node ./index.js watchlist imdb-watchlist.json
node ./index.js ratings imdb-ratings.json
