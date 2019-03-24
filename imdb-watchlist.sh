#!/bin/bash
# Usage: imdb-watchlist <IMDB_WATCHLIST_ID>
#   [{"id": "tt0111161"}]

set -eo pipefail

IMDB_WATCHLIST_ID=${1:-$IMDB_WATCHLIST_ID}

if [ -z "$IMDB_WATCHLIST_ID" ]; then
  sed -ne '/^#/!q;s/.\{1,2\}//;1d;p' < "$0"
  exit 1
fi

log() {
  COUNT=$(jq '. | length')
  if [ -n "$COUNT" ]; then
    echo "imdb-watchlist: $COUNT movies" >&2
  fi
}

curl --fail --silent \
    "https://www.imdb.com/list/$IMDB_WATCHLIST_ID/export" | \
  ./csvtojson.sh | \
  jq 'map({id: .Const})' | \
  tee >(log)
