#!/bin/bash

CONFIGS_PATH=0
if [ "$1" != "" ]; then
	CONFIGS_PATH=$1
else
  echo "[ERROR] Configs path not provided."
  exit 1
fi

NUM_OF_COMMANDS=0
if [ "$2" != "" ]; then
	NUM_OF_COMMANDS=$2
fi

LOG_FILE="$CONFIGS_PATH.logs.txt"
if [ "$3" != "" ]; then
	LOG_FILE=$3
fi

cd off-chain-api
python3.7 -O src/scripts/run_remote_perf.py \
	$CONFIGS_PATH $NUM_OF_COMMANDS > $LOG_FILE 2>&1
