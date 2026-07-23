#!/usr/bin/env bash
# ============================================================
# 여러 제출물을 한 과제로 일괄 채점하고 요약표 + 로그를 남긴다.
#
# 사용법: ./grade_all.sh <제출물들_상위폴더> [과제ID]
#   상위폴더 아래의 각 하위 디렉터리 = 제출물 1개
#   결과 로그: reports/<과제ID>/<제출물>.log
# ============================================================
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ROOT="${1:-}"
ASSIGNMENT="${2:-b2_1_budget_app}"
if [[ -z "$ROOT" || ! -d "$ROOT" ]]; then
  echo "사용법: ./grade_all.sh <제출물들_상위폴더> [과제ID]" >&2
  exit 2
fi
ROOT="$(cd "$ROOT" && pwd)"

LOGDIR="$HERE/reports/$ASSIGNMENT"
mkdir -p "$LOGDIR"

printf '%-34s %s\n' "제출물" "결과"
printf '%-34s %s\n' "----------------------------------" "----"
pass=0
fail=0
for dir in "$ROOT"/*/; do
  [[ -d "$dir" ]] || continue
  name="$(basename "$dir")"
  log="$LOGDIR/$name.log"
  if bash "$HERE/grade.sh" "$dir" "$ASSIGNMENT" >"$log" 2>&1; then
    printf '%-34s %s\n' "$name" "PASS"
    pass=$((pass + 1))
  else
    printf '%-34s %s\n' "$name" "FAIL  (reports/$ASSIGNMENT/$name.log)"
    fail=$((fail + 1))
  fi
done

echo
echo "완료: PASS $pass / FAIL $fail. 로그 폴더: $LOGDIR"
