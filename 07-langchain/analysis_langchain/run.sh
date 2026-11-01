#!/usr/bin/env bash
# Learn LangChain (s01~s10) launcher
# Usage: ./run.sh          run all lessons (offline, zero deps)
#        ./run.sh s04      run one lesson
set -u
cd "$(dirname "$0")"
export PYTHONIOENCODING=utf-8

if [ $# -gt 0 ]; then
    echo "==== $1 ===="
    python "$1/code.py"
    exit $?
fi

count=0
for d in s*/; do
    [ -f "${d}code.py" ] || continue
    echo
    echo "============================================================"
    echo " ${d%/}"
    echo "============================================================"
    python "${d}code.py" || { echo "[FAILED] ${d%/}"; exit 1; }
    count=$((count+1))
done
echo
echo "All ${count} lessons passed."
