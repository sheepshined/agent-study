#!/usr/bin/env bash
# Learn DeepSeek Harness (s01~s10) launcher
# Usage: ./run.sh          run all lessons (offline)
#        ./run.sh s06      run one lesson (add DEEPSEEK_API_KEY for real API demo)
set -u
cd "$(dirname "$0")"

if [ $# -gt 0 ]; then
    echo "==== $1 ===="
    node "$1/code.mjs"
    exit $?
fi

for d in s*/; do
    [ -f "${d}code.mjs" ] || continue
    echo
    echo "============================================================"
    echo " ${d%/}"
    echo "============================================================"
    node "${d}code.mjs" || { echo "[FAILED] ${d%/}"; exit 1; }
done
echo
echo "All 10 lessons passed."
