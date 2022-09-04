#!/bin/bash
# Usage: sync

[ -n "$RUNNER_DEBUG" ] && set -x

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

./diff-watchlist.sh movie | ./trakt-update-watchlist.sh movies
./diff-watchlist.sh show | ./trakt-update-watchlist.sh shows
./diff-ratings.sh movie | ./trakt-update-ratings.sh movies
./diff-ratings.sh show | ./trakt-update-ratings.sh shows
./diff-history.sh | ./trakt-update-history.sh
