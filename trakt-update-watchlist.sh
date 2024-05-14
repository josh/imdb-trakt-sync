#!/bin/bash
# Usage: trakt-update-watchlist [movies|shows] <TRAKT_CLIENT_ID> <TRAKT_ACCESS_TOKEN>

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

INPUT="/tmp/trakt-update-watchlist.json"
cat >"$INPUT"

if jq --exit-status '.add | length > 0' <"$INPUT" >/dev/null; then
	sleep 1
	jq '.add' <"$INPUT" |
		jq 'map({ids: {imdb: .id}})' |
		jq --arg type "$TYPE" '{($type): .}' |
		curl --fail "$curl_verbose" \
			--request POST \
			--header "Authorization: Bearer $TRAKT_ACCESS_TOKEN" \
			--header "Content-Type: application/json" \
			--header "trakt-api-version: 2" \
			--header "trakt-api-key: $TRAKT_CLIENT_ID" \
			--data-binary @- \
			"https://api.trakt.tv/sync/watchlist" |
		jq --arg type "$TYPE" '{added: .added[$type], existing: .existing[$type], not_found: .not_found[$type]}'
fi

if jq --exit-status '.remove | length > 0' <"$INPUT" >/dev/null; then
	sleep 1
	jq '.remove' <"$INPUT" |
		jq 'map({ids: {imdb: .id}})' |
		jq --arg type "$TYPE" '{($type): .}' |
		curl --fail "$curl_verbose" \
			--request POST \
			--header "Authorization: Bearer $TRAKT_ACCESS_TOKEN" \
			--header "Content-Type: application/json" \
			--header "trakt-api-version: 2" \
			--header "trakt-api-key: $TRAKT_CLIENT_ID" \
			--data-binary @- \
			"https://api.trakt.tv/sync/watchlist/remove" |
		jq --arg type "$TYPE" '{deleted: .deleted[$type], not_found: .not_found[$type]}'
fi

rm "$INPUT"
