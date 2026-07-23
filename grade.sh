#!/usr/bin/env bash
# ============================================================
# 한 구현체(내 것/남의 것)를 한 과제의 블랙박스 계약 테스트로 채점한다.
#
# 사용법:
#   ./grade.sh <대상_프로젝트_경로> [과제ID] [모듈명]
#     과제ID : assignments/ 아래 폴더명 (기본: b2_1_budget_app)
#     모듈명 : python -m <모듈> (생략 시 후보/__main__.py 로 자동탐지)
#
# 예:
#   ./grade.sh ~/Desktop/codyssey_B2-1                     # 내 과제
#   ./grade.sh ~/classmates/kim                            # 남의 과제(모듈 자동탐지)
#   ./grade.sh ~/classmates/lee b2_1_budget_app my_ledger  # 모듈명 직접 지정
# ============================================================
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

TARGET="${1:-}"
ASSIGNMENT="${2:-b2_1_budget_app}"
MODULE="${3:-}"

if [[ -z "$TARGET" ]]; then
  echo "사용법: ./grade.sh <대상_프로젝트_경로> [과제ID] [모듈명]" >&2
  exit 2
fi
if [[ ! -d "$TARGET" ]]; then
  echo "[!] 대상 경로가 없습니다: $TARGET" >&2
  exit 2
fi
TARGET="$(cd "$TARGET" && pwd)"

ADIR="$HERE/assignments/$ASSIGNMENT"
if [[ ! -d "$ADIR" ]]; then
  echo "[!] 그런 과제가 없습니다: $ASSIGNMENT" >&2
  echo "    사용 가능: $(ls "$HERE/assignments" 2>/dev/null | tr '\n' ' ')" >&2
  exit 2
fi

echo "==> 과제=$ASSIGNMENT  대상=$TARGET  모듈=${MODULE:-<자동탐지>}"

export TARGET_ROOT="$TARGET"
[[ -n "$MODULE" ]] && export TARGET_MODULE="$MODULE"
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8
# 계약(TestCase.txt)은 대상 것이 아니라 '그레이더 것'을 강제한다.
export TESTCASE_FILE="$ADIR/TestCase.txt"

cd "$HERE"
status=0

echo "==> pytest (블랙박스 계약)"
uv run pytest "assignments/$ASSIGNMENT" || status=$?

if [[ -f "$ADIR/smoke_test.py" ]]; then
  echo "==> smoke_test (표준 라이브러리만)"
  uv run python "$ADIR/smoke_test.py" || status=$?
fi

if [[ "$status" -eq 0 ]]; then
  echo "[PASS] $ASSIGNMENT — $TARGET"
else
  echo "[FAIL] $ASSIGNMENT — $TARGET (exit=$status)"
fi
exit "$status"
