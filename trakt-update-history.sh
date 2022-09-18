#!/bin/bash
# Usage: trakt-update-history <TRAKT_CLIENT_ID> <TRAKT_ACCESS_TOKEN>

set -eo pipefail
[ -n "$RUNNER_DEBUG" ] && set -x
[ -n "$RUNNER_DEBUG" ] && curl_verbose="--verbose" || curl_verbose="--silent"

TRAKT_CLIENT_ID=${1:-$TRAKT_CLIENT_ID}
TRAKT_ACCESS_TOKEN=${2:-$TRAKT_ACCESS_TOKEN}

if [ -z "$TRAKT_CLIENT_ID" ] || [ -z "$TRAKT_ACCESS_TOKEN" ]; then
	sed -ne '/^#/!q;s/.\{1,2\}//;1d;p' <"$0"
	exit 1
fi

INPUT="/tmp/trakt-update-history.json"
cat >"$INPUT"

if jq --exit-status '.add | length > 0' <"$INPUT" >/dev/null; then
	sleep 1
	jq '.add' <"$INPUT" |
		jq 'map({watched_at: .timestamp, ids: {imdb: .id}})' |
		jq '{movies: .}' |
		curl --fail "$curl_verbose" \
			--request POST \
			--header "Authorization: Bearer $TRAKT_ACCESS_TOKEN" \
			--header "Content-Type: application/json" \
			--header "trakt-api-version: 2" \
			--header "trakt-api-key: $TRAKT_CLIENT_ID" \
			--data-binary @- \
			"https://api.trakt.tv/sync/history" |
		jq '{added: .added.movies, not_found: .not_found.movies}'
fi

rm "$INPUT"
