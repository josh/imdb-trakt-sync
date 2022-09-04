#!/bin/bash
# Usage: imdb-trakt-sync <command>

[ -n "$ACTIONS_RUNNER_DEBUG" ] && set -x

COMMAND="$1"
shift

case "$COMMAND" in
diff-history | diff-ratings | diff-watchlist | imdb-ratings | imdb-watchlist | trakt-history | trakt-ratings | trakt-watchlist)
	exec "./$COMMAND.sh" "$@"
	;;
'' | sync)
	exec ./sync.sh
	;;
help | --help | -h | *)
	sed -ne '/^#/!q;s/.\{1,2\}//;1d;p' <"$0"
	exit 0
	;;
esac
