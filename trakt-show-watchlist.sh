#!/bin/bash
# Usage: trakt-show-watchlist <TRAKT_CLIENT_ID> <TRAKT_ACCESS_TOKEN>
#   [{"id": "tt0111161"}]

exec ./trakt-watchlist.sh show "$1"
