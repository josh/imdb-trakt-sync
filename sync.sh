#!/bin/bash
# Usage: sync

usage() {
	sed -ne '/^#/!q;s/.\{1,2\}//;1d;p' <"$0"
	exit 1
}

[ -n "$IMDB_UBID_MAIN" ] || usage
[ -n "$IMDB_AT_MAIN" ] || usage
[ -n "$IMDB_RATINGS_ID" ] || usage
[ -n "$IMDB_WATCHLIST_ID" ] || usage
[ -n "$TRAKT_ACCESS_TOKEN" ] || usage
[ -n "$TRAKT_CLIENT_ID" ] || usage

set -euxo pipefail

./diff-movie-watchlist.sh | ./trakt-update-watchlist.sh movies
./diff-show-watchlist.sh | ./trakt-update-watchlist.sh shows
./diff-ratings.sh | ./trakt-update-ratings.sh
./diff-history.sh | ./trakt-update-history.sh
