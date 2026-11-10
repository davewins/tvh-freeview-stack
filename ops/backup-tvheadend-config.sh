#!/bin/bash
# Back up the Tvheadend /config folder (channels, tuner scan, DVR profile, series rules, users, EPG settings) to a
# dated tar.gz, keeping the newest KEEP. Put DEST on another disk or machine, or let your backup tool pick the folder up.
# Usage: TVH_CONFIG_DIR=/srv/tvheadend/config DEST=/mnt/backup/tvheadend ./backup-tvheadend-config.sh
set -eu
SRC="${TVH_CONFIG_DIR:?set TVH_CONFIG_DIR}"; DEST="${DEST:?set DEST}"; KEEP="${KEEP:-14}"
mkdir -p "$DEST"
F="$DEST/tvheadend-config-$(date +%Y%m%d-%H%M%S).tar.gz"
# Tvheadend rewrites its files while running; a copy taken between writes is fine, a half-written one is rare. The EPG
# database and logs/cache are rebuilt automatically, so they are left out to keep the backup small.
tar -czf "$F" -C "$SRC" --exclude='epgdb.v*' --exclude='*.log' --exclude='cache' --exclude='timeshift' .
echo "wrote $F ($(du -h "$F" | cut -f1))"
ls -1t "$DEST"/tvheadend-config-*.tar.gz | tail -n +$((KEEP+1)) | xargs -r rm -f
