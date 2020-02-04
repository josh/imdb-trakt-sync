#!/bin/bash
# Usage: imdb-watchlist [movie|show] <IMDB_WATCHLIST_ID>
#   [{"id": "tt0111161"}]

set -eo pipefail

TYPE=${1}
IMDB_WATCHLIST_ID=${2:-$IMDB_WATCHLIST_ID}

if [ -z "$IMDB_WATCHLIST_ID" ]; then
	sed -ne '/^#/!q;s/.\{1,2\}//;1d;p' <"$0"
	exit 1
fi

if [ "$TYPE" == "movie" ]; then
	TITLE_TYPE="movie"
elif [ "$TYPE" == "show" ]; then
	TITLE_TYPE="tvSeries"
else
	sed -ne '/^#/!q;s/.\{1,2\}//;1d;p' <"$0"
	exit 1
fi

log() {
	COUNT=$(jq '. | length')
	if [[ "$COUNT" -ne 0 ]]; then
		echo "imdb-watchlist: $COUNT ${TYPE}s" >&2
	fi
}

curl --fail --silent \
	"https://www.imdb.com/list/$IMDB_WATCHLIST_ID/export" |
	./csvtojson.sh |
	jq --arg type "$TITLE_TYPE" 'map(select(.["Title Type"] == $type) | {id: .Const}) | if length == 0 then halt_error(1) else . end' |
	tee >(log)
