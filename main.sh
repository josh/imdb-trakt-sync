#!/bin/bash
# Usage: imdb-trakt-sync <command>

COMMAND="$1"
shift

case "$COMMAND" in
imdb-ratings )
  exec ./imdb-ratings.sh "$@"
  ;;
imdb-watchlist )
  exec ./imdb-watchlist.sh "$@"
  ;;
trakt-history )
  exec ./trakt-history.sh "$@"
  ;;
trakt-ratings )
  exec ./trakt-ratings.sh "$@"
  ;;
trakt-watchlist )
  exec ./trakt-watchlist.sh "$@"
  ;;
diff-ratings )
  exec ./diff-ratings.sh "$@"
  ;;
diff-watchlist )
  exec ./diff-watchlist.sh "$@"
  ;;
'' | sync )
  exec ./sync.sh
  ;;
help | --help | -h | * )
  sed -ne '/^#/!q;s/.\{1,2\}//;1d;p' < "$0"
  exit 0
  ;;
esac
