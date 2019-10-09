#!/bin/bash
# Usage: imdb-show-watchlist <IMDB_WATCHLIST_ID>
#   [{"id": "tt0111161"}]

exec ./imdb-watchlist.sh show "$1"
