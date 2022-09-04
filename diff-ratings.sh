#!/bin/bash
# Usage: diff-ratings [movie|show]
#   {"add":[{"id": "tt0111161","rating":8,"timestamp":"2020-01-01T00:00:00Z"}], "remove":[]}

set -eo pipefail
[ -n "$RUNNER_DEBUG" ] && set -x

TYPE=${1}

log_add() {
	COUNT=$(jq '.add | length')
	if [ -n "$COUNT" ]; then
		echo "diff-ratings: add/update $COUNT ${TYPE}s" >&2
	fi
}

log_remove() {
	COUNT=$(jq '.remove | length')
	if [ -n "$COUNT" ]; then
		echo "diff-ratings: remove $COUNT ${TYPE}s" >&2
	fi
}

jq --exit-status --null-input \
	--slurpfile a <(./imdb-ratings.sh "$TYPE" "$IMDB_RATINGS_ID" "$IMDB_UBID_MAIN" "$IMDB_AT_MAIN") \
	--slurpfile b <(./trakt-ratings.sh "$TYPE" "$TRAKT_CLIENT_ID" "$TRAKT_ACCESS_TOKEN") '
if ($a | length == 0) then halt_error(1) else true end |
if ($b | length == 0) then halt_error(1) else true end |
($a[0] | map({key: .id, value: .}) | from_entries) as $a_set |
($b[0] | map({key: .id, value: .}) | from_entries) as $b_set |
{
  add: $a[0] | map(select(. != $b_set[.id])),
  remove: $b[0] | map(select($a_set[.id] == null))
}' |
	tee >(log_add) | tee >(log_remove)
