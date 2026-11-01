#!/usr/bin/env bash
# Learn OpenAI Codex (s01~s10) —— 零依赖、全离线，一键跑完全部课程代码。
# 用法：./run.sh          全跑（一课失败即停）
#       ./run.sh s07      单跑一课（可写 s07 或 s07_apply_patch）
set -u
cd "$(dirname "$0")"
export PYTHONIOENCODING=utf-8

if [ "$#" -ge 1 ]; then
  lesson="$1"
  [ -f "$lesson/code.py" ] || lesson="$(ls -d ${lesson}* 2>/dev/null | head -1)"
  echo "==== $lesson ===="
  python "$lesson/code.py"
  exit $?
fi

count=0
for dir in s*/; do
  dir="${dir%/}"
  [ -f "$dir/code.py" ] || continue
  echo ""
  echo "============================================================"
  echo " $dir / python code.py"
  echo "============================================================"
  if ! python "$dir/code.py"; then
    echo "[FAILED] $dir"
    exit 1
  fi
  count=$((count + 1))
done

echo ""
echo "All $count lessons passed."
