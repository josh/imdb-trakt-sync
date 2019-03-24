#!/bin/bash

if [[ -x ./node_modules/.bin/csvtojson ]]; then
  exec ./node_modules/.bin/csvtojson "$@"
else
  echo "missing csvtojson" >&2
  echo "" >&2
  echo "  $ npm install csvtojson" >&2
  echo "" >&2
  exit 1
fi
