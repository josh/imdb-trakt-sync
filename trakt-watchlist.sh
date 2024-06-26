#!/bin/bash
# Usage: trakt-watchlist [movie|show] <TRAKT_CLIENT_ID> <TRAKT_ACCESS_TOKEN>
#   [{"id": "tt0111161"}]

set -euo pipefail
[ -n "${RUNNER_DEBUG:-}" ] && set -x
[ -n "${RUNNER_DEBUG:-}" ] && curl_verbose="--verbose" || curl_verbose="--silent"

TYPE=${1}
TRAKT_CLIENT_ID=${2:-$TRAKT_CLIENT_ID}
TRAKT_ACCESS_TOKEN=${3:-$TRAKT_ACCESS_TOKEN}

if [ -z "$TRAKT_CLIENT_ID" ] || [ -z "$TRAKT_ACCESS_TOKEN" ]; then
	sed -ne '/^#/!q;s/.\{1,2\}//;1d;p' <"$0"
	exit 1
fi

log() {
	COUNT=$(jq '. | length')
	if [ -n "$COUNT" ]; then
		echo "trakt-watchlist: $COUNT ${TYPE}s" >&2
	fi
}

curl --fail "$curl_verbose" \
	--header "Authorization: Bearer $TRAKT_ACCESS_TOKEN" \
	--header "Content-Type: application/json" \
	--header "trakt-api-version: 2" \
	--header "trakt-api-key: $TRAKT_CLIENT_ID" \
	"https://api.trakt.tv/sync/watchlist/${TYPE}s" |
	jq --arg type "$TYPE" 'map({id: .[$type].ids.imdb}) | map(select(.id))' |
	tee >(log)
