"""B2-1 budget_app — 블랙박스 계약 테스트.

대상 앱을 서브프로세스로만 구동하므로(내부 import 없음) 다른 사람의 구현에도
그대로 적용된다. 사람이 읽는 문구는 단언하지 않고, 명세가 고정한 것
(종료 코드 / 저장 파일 / CSV 스키마 / 데이터 보존)만 단언한다.

- ``@pytest.mark.contract`` : 명세가 요구하는 필수 계약 — 어떤 구현이든 통과해야 함
- ``@pytest.mark.optional`` : 구현마다 다를 수 있는 확장 — 미지원 시 skip
"""

from __future__ import annotations

import csv
import io
import os
import re
from pathlib import Path

import pytest
from blackbox import (
    assert_no_traceback,
    data_files,
    discover_option,
    load_testcases,
    require_option,
    write_csv,
)

# 과제 명세가 고정한 CSV 필수 컬럼
REQUIRED_CSV_COLUMNS = ("date", "type", "category", "amount")

# 체크리스트가 요구하는 명령 집합
REQUIRED_COMMANDS = ("add", "list", "search", "summary", "export", "import", "update", "delete")

# 시드 데이터(sample_csv)에서 파생되는 기대값
SEED_INCOME = 3000000
SEED_EXPENSE = 165000  # 15000 + 150000
SEED_MONTH = "2024-01"


def norm(text: str) -> str:
    """금액 표기 차이를 흡수한다: '3,000,000' → '3000000'."""
    return re.sub(r"(?<=\d),(?=\d)", "", text)


def first_tx_id(text: str) -> str | None:
    """목록 출력에서 '<접두어>-<숫자>' 형태의 거래 ID 로 보이는 첫 토큰."""
    m = re.search(r"\b([A-Za-z]{1,6}-\d{1,12})\b", text)
    return m.group(1) if m else None


# ============================================================
# 종료 코드 계약 (TestCase.txt)
# ============================================================


def _testcase_path() -> Path:
    """계약 파일 경로 — grade.sh 가 준 TESTCASE_FILE 우선, 없으면 이 폴더의 것."""
    env = os.environ.get("TESTCASE_FILE", "").strip()
    if env:
        return Path(env)
    return Path(__file__).parent / "TestCase.txt"


_CASES = load_testcases(_testcase_path())


@pytest.mark.contract
@pytest.mark.skipif(not _CASES, reason="TestCase.txt 에 유효한 케이스가 없습니다.")
@pytest.mark.parametrize(
    "args,expected", _CASES, ids=[f"{' '.join(a)} => {e}" for a, e in _CASES]
)
def test_exit_code_contract(cli, args, expected):
    proc = cli.run(*args)
    out = cli.output(proc)
    assert_no_traceback(out)
    if expected == "!0":
        assert proc.returncode != 0, (
            f"`{' '.join(args)}` 는 오류로 끝나야 하는데 종료 코드가 0입니다.\n{out}"
        )
    else:
        assert proc.returncode == int(expected), (
            f"`{' '.join(args)}` 기대 종료 코드 {expected}, 실제 {proc.returncode}\n{out}"
        )


# ============================================================
# 1.1 명령 존재 및 동작
# ============================================================


@pytest.mark.contract
def test_help_lists_required_commands(cli):
    proc = cli.run("--help")
    out = cli.output(proc)
    assert proc.returncode == 0, f"--help 가 실패했습니다:\n{out}"
    missing = [c for c in REQUIRED_COMMANDS if not re.search(rf"(?<![\w-]){c}(?![\w-])", out)]
    assert not missing, f"help 에 노출되지 않은 필수 명령: {missing}\n{out}"


@pytest.mark.contract
def test_list_runs_and_shows_seeded_data(cli, seed):
    seed()
    proc = cli.run("list")
    out = cli.output(proc)
    assert proc.returncode == 0, f"list 실패:\n{out}"
    assert_no_traceback(out)
    assert "lunchmemo" in out, f"list 출력에 시드 거래가 보이지 않습니다:\n{out}"


@pytest.mark.contract
def test_search_filters_by_category(cli, seed):
    seed()
    opt = require_option(cli.help_of("search"), ["--category", "--cat"], "search 카테고리")
    proc = cli.run("search", opt, "food")
    out = cli.output(proc)
    assert proc.returncode == 0, f"search 실패:\n{out}"
    assert_no_traceback(out)
    assert "lunchmemo" in out, f"food 카테고리 거래가 검색되지 않았습니다:\n{out}"
    assert "rentmemo" not in out, f"필터가 적용되지 않아 rent 거래까지 나왔습니다:\n{out}"


@pytest.mark.contract
def test_summary_reports_income_and_expense(cli, seed):
    seed()
    opt = require_option(cli.help_of("summary"), ["--month", "-m"], "summary 월")
    proc = cli.run("summary", opt, SEED_MONTH)
    out = norm(cli.output(proc))
    assert proc.returncode == 0, f"summary 실패:\n{out}"
    assert_no_traceback(out)
    assert str(SEED_INCOME) in out, f"총 수입 {SEED_INCOME} 이 보이지 않습니다:\n{out}"
    assert str(SEED_EXPENSE) in out, f"총 지출 {SEED_EXPENSE} 가 보이지 않습니다:\n{out}"


@pytest.mark.optional
def test_add_interactive_persists_transaction(cli, seed):
    """add 대화형 입력 — 프롬프트 순서는 구현마다 다를 수 있어 optional."""
    seed()  # 카테고리(food)가 등록된 상태를 만든다
    stdin = "2024-03-01\nexpense\nfood\n77777\naddedmemo\n\n"
    proc = cli.run("add", stdin=stdin)
    out = cli.output(proc)
    assert_no_traceback(out)
    if proc.returncode != 0:
        pytest.skip(f"대화형 add 의 프롬프트 순서가 명세와 다른 것으로 보입니다 (rc={proc.returncode})")
    listed = norm(cli.output(cli.run("list")))
    assert "77777" in listed, f"add 로 넣은 거래가 목록에 없습니다:\n{listed}"


# ============================================================
# 1.2 영속성
# ============================================================


@pytest.mark.contract
def test_data_persists_across_process_restarts(cli, seed):
    seed()
    proc = cli.run("list")  # 완전히 새로운 프로세스 — 파일에서 읽어야 통과
    out = cli.output(proc)
    assert proc.returncode == 0, f"재실행 list 실패:\n{out}"
    assert "lunchmemo" in out, "재실행 후 거래 데이터가 유지되지 않았습니다."

    files = data_files(cli.data_dir)
    assert len(files) >= 3, (
        f"저장 파일이 3개 미만입니다(거래/카테고리/예산 분리 필요): {[f.name for f in files]}"
    )


# ============================================================
# 1.3 카테고리
# ============================================================


@pytest.mark.contract
def test_category_add_list_remove(cli):
    add_opt = require_option(cli.help_of("category", "add"), ["--name", "-n"], "category add 이름")
    assert cli.run("category", "add", add_opt, "groceries").returncode == 0

    listed = cli.output(cli.run("category", "list"))
    assert "groceries" in listed, f"추가한 카테고리가 목록에 없습니다:\n{listed}"

    rem_opt = require_option(
        cli.help_of("category", "remove"), ["--name", "-n"], "category remove 이름"
    )
    proc = cli.run("category", "remove", rem_opt, "groceries")
    assert proc.returncode == 0, f"미사용 카테고리 삭제 실패:\n{cli.output(proc)}"
    assert "groceries" not in cli.output(cli.run("category", "list"))


@pytest.mark.contract
def test_category_remove_in_use_never_loses_data(cli, seed):
    """사용 중 카테고리 삭제 시 거래가 조용히 사라지면 안 된다(정책은 구현 자유)."""
    seed()
    before = cli.output(cli.run("list"))
    assert "lunchmemo" in before

    rem_opt = require_option(
        cli.help_of("category", "remove"), ["--name", "-n"], "category remove 이름"
    )
    proc = cli.run("category", "remove", rem_opt, "food")  # food 는 사용 중
    out = cli.output(proc)
    assert_no_traceback(out)

    after = cli.output(cli.run("list"))
    assert "lunchmemo" in after, (
        "사용 중 카테고리를 삭제하면서 거래가 사라졌습니다. "
        "차단하거나 대체 카테고리로 재지정해야 합니다.\n" + out
    )
    if proc.returncode == 0:
        assert "food" not in cli.output(cli.run("category", "list")), (
            "삭제 성공(rc=0)이라면서 카테고리가 그대로 남아 있습니다."
        )


# ============================================================
# 1.4 예산
# ============================================================


@pytest.mark.contract
def test_budget_set_and_summary_shows_usage(cli, seed):
    seed()
    bhelp = cli.help_of("budget", "set")
    m_opt = require_option(bhelp, ["--month", "-m"], "budget 월")
    a_opt = require_option(bhelp, ["--amount", "-a"], "budget 금액")
    proc = cli.run("budget", "set", m_opt, SEED_MONTH, a_opt, "500000")
    assert proc.returncode == 0, f"budget set 실패:\n{cli.output(proc)}"

    s_opt = require_option(cli.help_of("summary"), ["--month", "-m"], "summary 월")
    out = norm(cli.output(cli.run("summary", s_opt, SEED_MONTH)))
    assert "500000" in out, f"summary 에 예산액이 보이지 않습니다:\n{out}"
    assert "33" in out, f"summary 에 예산 사용률(33%)이 보이지 않습니다:\n{out}"  # 165000/500000


@pytest.mark.contract
def test_summary_warns_when_over_budget(cli, seed):
    seed()
    bhelp = cli.help_of("budget", "set")
    m_opt = require_option(bhelp, ["--month", "-m"], "budget 월")
    a_opt = require_option(bhelp, ["--amount", "-a"], "budget 금액")
    assert cli.run("budget", "set", m_opt, SEED_MONTH, a_opt, "100000").returncode == 0

    s_opt = require_option(cli.help_of("summary"), ["--month", "-m"], "summary 월")
    out = norm(cli.output(cli.run("summary", s_opt, SEED_MONTH)))
    assert re.search(r"초과|경고|over|exceed", out, re.IGNORECASE), (
        f"예산 초과 상황인데 초과/경고 표시가 없습니다:\n{out}"
    )


# ============================================================
# 1.5 CSV 스키마 / 왕복
# ============================================================


@pytest.mark.contract
def test_export_csv_is_utf8_with_header_and_columns(cli, seed, workdir: Path):
    seed()
    ehelp = cli.help_of("export")
    out_opt = require_option(ehelp, ["--out", "--to", "--file", "--output"], "export 출력")
    target = workdir / "export_check.csv"

    args = ["export", out_opt, str(target)]
    if (month_opt := discover_option(ehelp, ["--month"])) is not None:
        args += [month_opt, SEED_MONTH]
    proc = cli.run(*args)
    out = cli.output(proc)
    assert proc.returncode == 0, f"export 실패:\n{out}"
    assert target.exists(), f"export 파일이 생성되지 않았습니다: {target}"

    text = target.read_bytes().decode("utf-8")  # UnicodeDecodeError 면 실패
    reader = csv.DictReader(io.StringIO(text))
    fields = [f.lstrip("﻿") for f in (reader.fieldnames or [])]
    assert fields, "CSV 에 헤더가 없습니다."
    missing = [c for c in REQUIRED_CSV_COLUMNS if c not in fields]
    assert not missing, f"CSV 헤더에 필수 컬럼이 없습니다: {missing} (실제: {fields})"
    assert list(reader), "export 결과에 데이터 행이 없습니다."


@pytest.mark.contract
def test_import_export_roundtrip_preserves_rows(cli, seed, workdir: Path):
    """import 한 3건이 export 로 그대로 나와야 한다(왕복 안전성)."""
    seed()
    ehelp = cli.help_of("export")
    out_opt = require_option(ehelp, ["--out", "--to", "--file", "--output"], "export 출력")
    target = workdir / "roundtrip.csv"

    args = ["export", out_opt, str(target)]
    if (month_opt := discover_option(ehelp, ["--month"])) is not None:
        args += [month_opt, SEED_MONTH]
    assert cli.run(*args).returncode == 0

    rows = list(csv.DictReader(io.StringIO(target.read_text(encoding="utf-8"))))
    assert len(rows) == 3, f"import 3건 → export {len(rows)}건 (건수 불일치)"
    amounts = sorted(int(r["amount"]) for r in rows)
    assert amounts == [15000, 150000, 3000000], f"금액이 보존되지 않았습니다: {amounts}"


# ============================================================
# 1.6 / 1.7 오류 처리와 종료 코드
# ============================================================


@pytest.mark.contract
def test_invalid_argument_exits_nonzero_without_traceback(cli):
    opt = require_option(cli.help_of("summary"), ["--month", "-m"], "summary 월")
    proc = cli.run("summary", opt, "2024-13")  # 13월은 존재하지 않음
    out = cli.output(proc)
    assert_no_traceback(out)
    assert proc.returncode != 0, f"잘못된 월인데 종료 코드가 0입니다:\n{out}"


@pytest.mark.contract
def test_missing_file_exits_nonzero_without_traceback(cli, workdir: Path):
    opt = require_option(cli.help_of("import"), ["--from", "--file", "--in", "--input"], "import 입력")
    proc = cli.run("import", opt, str(workdir / "does_not_exist.csv"))
    out = cli.output(proc)
    assert_no_traceback(out)
    assert proc.returncode != 0, f"없는 파일인데 종료 코드가 0입니다:\n{out}"


@pytest.mark.contract
def test_error_output_gives_a_hint(cli):
    """오류 시 원인만이 아니라 해결 힌트를 제시하는가(문구는 구현 자유)."""
    opt = require_option(cli.help_of("summary"), ["--month", "-m"], "summary 월")
    out = cli.output(cli.run("summary", opt, "2024-13"))
    assert re.search(r"힌트|hint|확인|usage|사용법|예:", out, re.IGNORECASE), (
        f"오류 출력에 해결 힌트가 없습니다:\n{out}"
    )


@pytest.mark.contract
def test_delete_unknown_id_exits_nonzero(cli, seed):
    seed()
    opt = require_option(cli.help_of("delete"), ["--id", "-i"], "delete id")
    proc = cli.run("delete", opt, "NOPE-999999")
    out = cli.output(proc)
    assert_no_traceback(out)
    assert proc.returncode != 0, f"없는 id 삭제인데 종료 코드가 0입니다:\n{out}"


# ============================================================
# update / delete 반영
# ============================================================


@pytest.mark.contract
def test_update_changes_field_and_persists(cli, seed):
    seed()
    tx_id = first_tx_id(cli.output(cli.run("list")))
    if tx_id is None:
        pytest.skip("목록에서 거래 ID 형식(<접두어>-<숫자>)을 찾지 못했습니다.")

    uhelp = cli.help_of("update")
    id_opt = require_option(uhelp, ["--id", "-i"], "update id")
    amt_opt = require_option(uhelp, ["--amount", "-a"], "update 금액")
    proc = cli.run("update", id_opt, tx_id, amt_opt, "24680")
    out = cli.output(proc)
    assert proc.returncode == 0, f"update 실패:\n{out}"
    assert_no_traceback(out)

    after = norm(cli.output(cli.run("list")))
    assert "24680" in after, f"update 한 금액이 반영되지 않았습니다:\n{after}"


@pytest.mark.contract
def test_delete_removes_transaction(cli, seed):
    seed()
    tx_id = first_tx_id(cli.output(cli.run("list")))
    if tx_id is None:
        pytest.skip("목록에서 거래 ID 를 찾지 못했습니다.")

    opt = require_option(cli.help_of("delete"), ["--id", "-i"], "delete id")
    assert cli.run("delete", opt, tx_id).returncode == 0
    after = cli.output(cli.run("list"))
    assert tx_id not in after, f"삭제한 거래가 목록에 남아 있습니다:\n{after}"


# ============================================================
# 깨진 CSV 처리 정책 (부분 성공 or 전수 롤백 — 어느 쪽이든 '어중간' 금지)
# ============================================================


@pytest.mark.contract
def test_import_with_broken_rows_is_consistent(cli, workdir: Path):
    csv_path = write_csv(
        workdir / "broken.csv",
        [
            "2024-05-01,expense,food,5000,goodrow,",
            "2024-05-02,expense,food,-3,brokenrow,",  # 음수 금액 → 무효
            "2024-05-03,income,salary,7000,goodrow2,",
        ],
        "date,type,category,amount,memo,tags",
    )
    opt = require_option(cli.help_of("import"), ["--from", "--file", "--in", "--input"], "import 입력")
    proc = cli.run("import", opt, str(csv_path))
    out = cli.output(proc)
    assert_no_traceback(out)

    listed = cli.output(cli.run("list"))
    good_saved = "goodrow" in listed
    broken_saved = "brokenrow" in listed
    assert not broken_saved, f"무효한 행(-3원)이 저장되었습니다:\n{listed}"

    if proc.returncode == 0:
        assert good_saved, f"부분 성공(rc=0)인데 유효 행이 저장되지 않았습니다:\n{listed}"
        assert re.search(r"skip|건너|무시|오류|error|실패", out, re.IGNORECASE), (
            f"건너뛴 행에 대한 리포트가 없습니다:\n{out}"
        )
    else:
        assert not good_saved, (
            f"실패(rc={proc.returncode})로 보고했지만 일부 행이 저장되어 있습니다"
            f"(부분 반영 = 롤백 실패):\n{listed}"
        )
