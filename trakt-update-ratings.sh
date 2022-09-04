#!/bin/bash
# Usage: trakt-update-ratings [movies|shows] <TRAKT_CLIENT_ID> <TRAKT_ACCESS_TOKEN>

set -eo pipefail
[ -n "$ACTIONS_RUNNER_DEBUG" ] && set -x
[ -n "$ACTIONS_RUNNER_DEBUG" ] && curl_verbose="--verbose" || curl_verbose="--silent"

TYPE=${1}
TRAKT_CLIENT_ID=${2:-$TRAKT_CLIENT_ID}
TRAKT_ACCESS_TOKEN=${3:-$TRAKT_ACCESS_TOKEN}

if [ -z "$TRAKT_CLIENT_ID" ] || [ -z "$TRAKT_ACCESS_TOKEN" ]; then
	sed -ne '/^#/!q;s/.\{1,2\}//;1d;p' <"$0"
	exit 1
fi

cat >/tmp/trakt-update-ratings.json

sleep 1
jq '.add' </tmp/trakt-update-ratings.json |
	jq 'map({rating: .rating, rated_at: .timestamp, ids: {imdb: .id}})' |
	jq --arg type "$TYPE" '{($type): .}' |
	curl --fail "$curl_verbose" \
		--request POST \
		--header "Authorization: Bearer $TRAKT_ACCESS_TOKEN" \
		--header "Content-Type: application/json" \
		--header "trakt-api-version: 2" \
		--header "trakt-api-key: $TRAKT_CLIENT_ID" \
		--data-binary @- \
		"https://api.trakt.tv/sync/ratings" |
	jq --arg type "$TYPE" '{added: .added[$type], not_found: .not_found[$type]}'

sleep 1
jq '.remove' </tmp/trakt-update-ratings.json |
	jq 'map({ids: {imdb: .id}})' |
	jq --arg type "$TYPE" '{($type): .}' |
	curl --fail "$curl_verbose" \
		--request POST \
		--header "Authorization: Bearer $TRAKT_ACCESS_TOKEN" \
		--header "Content-Type: application/json" \
		--header "trakt-api-version: 2" \
		--header "trakt-api-key: $TRAKT_CLIENT_ID" \
		--data-binary @- \
		"https://api.trakt.tv/sync/ratings/remove" |
	jq --arg type "$TYPE" '{deleted: .deleted[$type], not_found: .not_found[$type]}'

rm /tmp/trakt-update-ratings.json
