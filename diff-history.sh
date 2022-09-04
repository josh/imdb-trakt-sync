#!/bin/bash
# Usage: diff-history
#   {"add":[{"id": "tt0111161","timestamp":"2020-01-01T00:00:00Z"}]}

set -eo pipefail
[ -n "$RUNNER_DEBUG" ] && set -x

log_add() {
	COUNT=$(jq '.add | length')
	if [ -n "$COUNT" ]; then
		echo "diff-history: add $COUNT movies" >&2
	fi
}

jq --exit-status --null-input \
	--slurpfile a <(./imdb-ratings.sh movie "$IMDB_RATINGS_ID" "$IMDB_UBID_MAIN" "$IMDB_AT_MAIN") \
	--slurpfile b <(./trakt-history.sh "$TRAKT_CLIENT_ID" "$TRAKT_ACCESS_TOKEN") '
if ($a | length == 0) then halt_error(1) else true end |
if ($b | length == 0) then halt_error(1) else true end |
($a[0] | map({key: .id, value: .timestamp}) | from_entries) as $a_set |
($b[0] | map({key: .id, value: .timestamp}) | from_entries) as $b_set |
{
  add: $a[0] | map(select($b_set[.id] == null)) | map({id: .id, timestamp: .timestamp})
}' |
	tee >(log_add)
