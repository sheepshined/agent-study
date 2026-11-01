#!/usr/bin/env bash
# 一键跑完全部课程代码（只跑存在 code.py 的 s* 目录，跳过 shared/）。
# 用法：./run.sh   （或在 Windows 上 cmd /c run.bat）
set -u
cd "$(dirname "$0")"
export PYTHONIOENCODING=utf-8   # Windows 控制台默认 GBK，图解符号会炸 UnicodeEncodeError

pass=0
fail=0
for dir in s*/; do
  dir="${dir%/}"
  [ -f "$dir/code.py" ] || continue
  echo "==================== $dir / python code.py ===================="
  if python "$dir/code.py" > /dev/null; then
    echo "[PASS] $dir"
    pass=$((pass + 1))
  else
    echo "[FAIL] $dir"
    python "$dir/code.py"   # 重跑一次，把报错打出来
    fail=$((fail + 1))
  fi
done

if [ "$fail" -eq 0 ]; then
  echo ""
  echo "All $pass lessons passed."
else
  echo ""
  echo "$fail lesson(s) FAILED, $pass passed."
  exit 1
fi
