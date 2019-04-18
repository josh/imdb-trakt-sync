#!/bin/bash
# Usage: trakt-ratings <TRAKT_CLIENT_ID> <TRAKT_ACCESS_TOKEN>
#   [{"id": "tt0111161", "rating": 10}]

set -eo pipefail

TRAKT_CLIENT_ID=${1:-$TRAKT_CLIENT_ID}
TRAKT_ACCESS_TOKEN=${2:-$TRAKT_ACCESS_TOKEN}

if [ -z "$TRAKT_CLIENT_ID" ] || [ -z "$TRAKT_ACCESS_TOKEN" ]; then
  sed -ne '/^#/!q;s/.\{1,2\}//;1d;p' < "$0"
  exit 1
fi

log() {
  COUNT=$(jq '. | length')
  if [ -n "$COUNT" ]; then
    echo "trakt-ratings: $COUNT movies" >&2
  fi
}

curl --fail --silent \
  --header "Authorization: Bearer $TRAKT_ACCESS_TOKEN" \
  --header "Content-Type: application/json" \
  --header "trakt-api-version: 2" \
  --header "trakt-api-key: $TRAKT_CLIENT_ID" \
  "https://api.trakt.tv/sync/ratings/movies" |
  jq 'map({
    id: .movie.ids.imdb,
    rating: .rating,
    timestamp: .rated_at
  }) | map(select(.id))' | \
  tee >(log)
