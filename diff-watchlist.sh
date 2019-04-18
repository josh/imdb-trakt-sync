#!/bin/bash
# Usage: diff-watchlist
#   {"add":[{"id": "tt0111161"}], "remove":[]}

set -eo pipefail

log_add() {
  COUNT=$(jq '.add | length')
  if [ -n "$COUNT" ]; then
    echo "diff-watchlist: add $COUNT movies" >&2
  fi
}

log_remove() {
  COUNT=$(jq '.remove | length')
  if [ -n "$COUNT" ]; then
    echo "diff-watchlist: remove $COUNT movies" >&2
  fi
}

A=$(./imdb-watchlist.sh "$IMDB_WATCHLIST_ID")
B=$(./trakt-watchlist.sh "$TRAKT_CLIENT_ID" "$TRAKT_ACCESS_TOKEN")

jq --exit-status --null-input \
  --argjson a "$A" \
  --argjson b "$B" '
($a | map(.id)) as $a_set |
($b | map(.id)) as $b_set |
{
  add: ($a_set - $b_set) | map({id: . }),
  remove: ($b_set - $a_set) | map({id: . })
}' | \
  tee >(log_add) | tee >(log_remove)
