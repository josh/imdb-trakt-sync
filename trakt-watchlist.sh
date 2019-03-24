#!/bin/bash
# Usage: trakt-watchlist <TRAKT_CLIENT_ID> <TRAKT_ACCESS_TOKEN>
#   [{"id": "tt0111161"}]

set -eo pipefail

if [ -z "$2" ]; then
  sed -ne '/^#/!q;s/.\{1,2\}//;1d;p' < "$0"
  exit 1
fi

log() {
  COUNT=$(jq '. | length')
  echo "trakt-watchlist: $COUNT movies" >&2
}

curl --fail --silent \
  --header "Authorization: Bearer $2" \
  --header "Content-Type: application/json" \
  --header "trakt-api-version: 2" \
  --header "trakt-api-key: $1" \
  "https://api.trakt.tv/sync/watchlist/movies" |
  jq 'map({id: .movie.ids.imdb}) | map(select(.id))' | \
  tee >(log)
