#!/bin/bash
# Usage: imdb-ratings <IMDB_RATINGS_ID> <IMDB_UBID_MAIN> <IMDB_AT_MAIN>
#   {"id": "tt0111161", "rating": 10, "timestamp": "2020-01-01T00:00:00Z"}

set -eo pipefail

IMDB_RATINGS_ID=${1:-$IMDB_RATINGS_ID}
IMDB_UBID_MAIN=${2:-$IMDB_UBID_MAIN}
IMDB_AT_MAIN=${3:-$IMDB_AT_MAIN}

if [ -z "$IMDB_RATINGS_ID" ] || [ -z "$IMDB_RATINGS_ID" ] || [ -z "$IMDB_AT_MAIN" ]; then
	sed -ne '/^#/!q;s/.\{1,2\}//;1d;p' <"$0"
	exit 1
fi

log() {
	COUNT=$(jq '. | length')
	if [[ "$COUNT" -ne 0 ]]; then
		echo "imdb-ratings: $COUNT movies" >&2
	fi
}

curl --fail --silent --cookie "ubid-main=$IMDB_UBID_MAIN; at-main=$IMDB_AT_MAIN" \
	"https://www.imdb.com/user/$IMDB_RATINGS_ID/ratings/export" |
	./csvtojson.sh |
	jq 'map({
    id: .Const,
    rating: .["Your Rating"] | tonumber,
    timestamp: .["Date Rated"] | strptime("%Y-%m-%d") | todateiso8601
  }) | if length == 0 then halt_error(1) else . end' |
	tee >(log)
