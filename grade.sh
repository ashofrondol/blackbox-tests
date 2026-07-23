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

# ---------- 보고서 경로 ----------
# 루트 conftest 의 리포트 플러그인이 이 경로에 'Markdown 보고서'를 남긴다.
# GRADE_REPORT="" 로 부르면(또는 NO_REPORT=1) 보고서를 끈다.
if [[ "${NO_REPORT:-0}" != "1" ]]; then
  REPORT_DIR="$HERE/reports/$ASSIGNMENT"
  mkdir -p "$REPORT_DIR"
  REPORT="$REPORT_DIR/$(basename "$TARGET")_$(date +%Y%m%d_%H%M%S).md"
  export GRADE_REPORT="$REPORT"
  export GRADE_ASSIGNMENT="$ASSIGNMENT"
fi

cd "$HERE"
status=0

echo "==> pytest (블랙박스 계약)"
uv run pytest "assignments/$ASSIGNMENT" || status=$?

smoke_rc=0
if [[ -f "$ADIR/smoke_test.py" ]]; then
  echo "==> smoke_test (표준 라이브러리만)"
  uv run python "$ADIR/smoke_test.py" || smoke_rc=$?
  [[ "$smoke_rc" -ne 0 ]] && status=$smoke_rc
fi

# 스모크 결과를 보고서 끝에 덧붙인다(플러그인은 pytest 부분만 기록).
if [[ -n "${REPORT:-}" && -f "$REPORT" ]]; then
  {
    printf '\n## 스모크 테스트 (핵심 경로 1회 관통)\n'
    if [[ "$smoke_rc" -eq 0 ]]; then
      printf -- '- ✅ 통과\n'
    else
      printf -- '- ❌ 실패 (exit=%s) — 콘솔 로그의 [FAIL] 단계를 확인하세요\n' "$smoke_rc"
    fi
  } >> "$REPORT"
fi

if [[ "$status" -eq 0 ]]; then
  echo "[PASS] $ASSIGNMENT — $TARGET"
else
  echo "[FAIL] $ASSIGNMENT — $TARGET (exit=$status)"
fi
[[ -n "${REPORT:-}" && -f "$REPORT" ]] && echo "[보고서] $REPORT"
exit "$status"
