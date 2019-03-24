#!/bin/bash
# Usage: imdb-ratings <IMDB_RATINGS_ID> <IMDB_ID> <IMDB_SID>
#   {"id": "tt0111161", "rating": 10, "timestamp": "2020-01-01T00:00:00Z"}

set -eo pipefail

if [ -z "$3" ]; then
  sed -ne '/^#/!q;s/.\{1,2\}//;1d;p' < "$0"
  exit 1
fi

curl --fail --silent --cookie "id=$2; sid=$3" \
    "https://www.imdb.com/user/$1/ratings/export" | \
  ./csvtojson.sh | \
  jq 'map({
    id: .Const,
    rating: .["Your Rating"] | tonumber,
    timestamp: .["Date Rated"] | strptime("%Y-%m-%d") | todateiso8601
  })'
