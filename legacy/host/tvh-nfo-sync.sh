#!/bin/bash
# Host wrapper: runs tvh-nfo-sync.py inside the tvheadend container as uid 1000. Cron every 10 min.
LOG=${TVH_STACK_DIR:-/opt/tvh-freeview-stack}/legacy/host/tvh-nfo-sync.log
D=${TVH_STACK_DIR:-/opt/tvh-freeview-stack}
U=$(head -1 $D/.tvheadend-credentials | cut -d: -f1); P=$(head -1 $D/.tvheadend-credentials | cut -d: -f2-)
OUT=$(docker exec -u 1000 -i -e TVH_USER="$U" -e TVH_PASS="$P" tvheadend python3 - < $D/scripts/tvh-nfo-sync.py 2>&1); RC=$?
echo "$(date '+%F %T') rc=$RC $OUT" | tail -c 600 >> $LOG
[ $(wc -l < $LOG) -gt 500 ] && tail -200 $LOG > $LOG.t && mv $LOG.t $LOG
FB=$(/usr/bin/python3 -I $D/scripts/tvh-series-image-fallback.py 2>&1 | tail -c 300); echo "$(date '+%F %T') image-fallback: $FB" >> $LOG
exit $RC
