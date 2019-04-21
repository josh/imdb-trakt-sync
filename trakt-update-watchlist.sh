#!/bin/bash
# Usage: trakt-update-watchlist <TRAKT_CLIENT_ID> <TRAKT_ACCESS_TOKEN>

set -eo pipefail

TRAKT_CLIENT_ID=${1:-$TRAKT_CLIENT_ID}
TRAKT_ACCESS_TOKEN=${2:-$TRAKT_ACCESS_TOKEN}

if [ -z "$TRAKT_CLIENT_ID" ] || [ -z "$TRAKT_ACCESS_TOKEN" ]; then
  sed -ne '/^#/!q;s/.\{1,2\}//;1d;p' < "$0"
  exit 1
fi

cat >/tmp/trakt-update-watchlist.json

jq '.add' </tmp/trakt-update-watchlist.json | \
  jq 'map({ids: {imdb: .id}})' | \
  jq '{movies: .}' | \
  curl --fail --silent \
    --request POST \
    --header "Authorization: Bearer $TRAKT_ACCESS_TOKEN" \
    --header "Content-Type: application/json" \
    --header "trakt-api-version: 2" \
    --header "trakt-api-key: $TRAKT_CLIENT_ID" \
    --data-binary @- \
    "https://api.trakt.tv/sync/watchlist" | \
  jq '{added: .added.movies, existing: .existing.movies, not_found: .not_found.movies}'

jq '.remove' </tmp/trakt-update-watchlist.json | \
  jq 'map({ids: {imdb: .id}})' | \
  jq '{movies: .}' | \
  curl --fail --silent \
    --request POST \
    --header "Authorization: Bearer $TRAKT_ACCESS_TOKEN" \
    --header "Content-Type: application/json" \
    --header "trakt-api-version: 2" \
    --header "trakt-api-key: $TRAKT_CLIENT_ID" \
    --data-binary @- \
    "https://api.trakt.tv/sync/watchlist/remove" | \
  jq '{deleted: .deleted.movies, not_found: .not_found.movies}'

rm /tmp/trakt-update-watchlist.json
