#!/bin/bash
# Usage: imdb-watchlist <IMDB_WATCHLIST_ID>
#   [{"id": "tt0111161"}]

set -eo pipefail

if [ -z "$1" ]; then
  sed -ne '/^#/!q;s/.\{1,2\}//;1d;p' < "$0"
  exit 1
fi

log() {
  COUNT=$(jq '. | length')
  echo "imdb-watchlist: $COUNT movies" >&2
}

curl --fail --silent \
    "https://www.imdb.com/list/$IMDB_WATCHLIST_ID/export" | \
  ./csvtojson.sh | \
  jq 'map({id: .Const})' | \
  tee >(log)
