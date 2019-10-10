#!/bin/bash
# Usage: trakt-movie-watchlist <TRAKT_CLIENT_ID> <TRAKT_ACCESS_TOKEN>
#   [{"id": "tt0111161"}]

exec ./trakt-watchlist.sh movie "$1"
