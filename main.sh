#!/bin/bash
# Usage: imdb-trakt-sync <command>

case "$1" in
help | --help | -h )
  sed -ne '/^#/!q;s/.\{1,2\}//;1d;p' < "$0"
  exit 0
  ;;
imdb-ratings )
  exec ./imdb-ratings.sh "$@"
  ;;
imdb-watchlist )
  exec ./imdb-watchlist.sh "$@"
  ;;
* )
  exec ./sync.sh
  ;;
esac
