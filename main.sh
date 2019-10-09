#!/bin/bash
# Usage: imdb-trakt-sync <command>

COMMAND="$1"
shift

case "$COMMAND" in
diff-history | diff-ratings | diff-movie-watchlist | imdb-ratings | imdb-movie-watchlist | trakt-history | trakt-ratings | trakt-movie-watchlist )
  exec "./$COMMAND.sh" "$@"
  ;;
'' | sync )
  exec ./sync.sh
  ;;
help | --help | -h | * )
  sed -ne '/^#/!q;s/.\{1,2\}//;1d;p' < "$0"
  exit 0
  ;;
esac
