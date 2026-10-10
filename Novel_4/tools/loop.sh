#!/bin/bash
# usage: TOOL=compe tools/loop.sh <args...> ; CONTINUE が出なくなるまで再実行（176秒まで。この環境の1回の上限に合わせる）
end=$((SECONDS+176))
while [ $SECONDS -lt $end ]; do
  out=$(timeout $((end-SECONDS)) python3 tools/${TOOL:-evolve}.py "$@" 2>&1); rc=$?
  echo "$out" | grep -v "^CONTINUE"
  echo "$out" | grep -q "^CONTINUE" || { echo "[rc=$rc]"; exit $rc; }
done
echo "[時間切れ。もう一度]"
