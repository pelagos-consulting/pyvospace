#!/usr/bin/env bash
logfile=$PYVOSPACE_DIR/scripts/log/ngas.log
ngamsServer -force -cfg ${NGAS_STORAGE_DIR}/cfg/ngamsServer.conf -v 4 -autoonline 2>&1 | tee $logfile
