#!/bin/sh
set -eu
mkdir -p /data/pmdf
if [ ! -d /data/pmdf/.git ]; then
  git init /data/pmdf
fi
exec sleep infinity
