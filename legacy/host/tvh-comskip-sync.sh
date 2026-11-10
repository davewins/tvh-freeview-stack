#!/bin/bash
# Cron wrapper (every 10 min): Comskip advert breaks -> chapters in new Freeview recordings. See tvh-comskip-sync.py.
D=${TVH_STACK_DIR:-/opt/tvh-freeview-stack}/legacy/host
LOG=$D/tvh-comskip-sync.log
nice -n 15 /usr/bin/python3 -I $D/tvh-comskip-sync.py >> $LOG 2>&1
[ "$(wc -l < $LOG)" -gt 500 ] && tail -200 $LOG > $LOG.t && mv $LOG.t $LOG
exit 0
