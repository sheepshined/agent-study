#!/usr/bin/env bash
# Learn OpenClaw (s01~s10) launcher
# Usage: ./run.sh          run all lessons (offline)
#        ./run.sh s03      run one lesson
set -u
cd "$(dirname "$0")"

if [ $# -gt 0 ]; then
    echo "==== $1 ===="
    node "$1/code.mjs"
    exit $?
fi

count=0
for d in s*/; do
    [ -f "${d}code.mjs" ] || continue
    echo
    echo "============================================================"
    echo " ${d%/}"
    echo "============================================================"
    node "${d}code.mjs" || { echo "[FAILED] ${d%/}"; exit 1; }
    count=$((count+1))
done
echo
echo "All ${count} lessons passed."
