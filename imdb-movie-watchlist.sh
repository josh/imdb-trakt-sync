#!/bin/bash
# Usage: imdb-movie-watchlist <IMDB_WATCHLIST_ID>
#   [{"id": "tt0111161"}]

exec ./imdb-watchlist.sh movie "$1"
