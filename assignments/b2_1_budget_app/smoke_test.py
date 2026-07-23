"""B2-1 budget_app 스모크 테스트 — 핵심 경로를 끝까지 한 번 훑는다.

pytest 없이 표준 라이브러리만으로 동작하므로, 의존성이 없는 환경에서도 돌아간다.
공용 하네스(shared/blackbox.py)를 sys.path 에 얹어 대상 자동탐지/실행을 재사용한다.

    TARGET_ROOT=/path/to/app  python smoke_test.py
    TARGET_MODULE=my_ledger   python smoke_test.py   # 모듈명이 다를 때
"""

from __future__ import annotations

import csv
import io
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# shared/blackbox.py 를 import 경로에 얹는다 (assignments/<id>/ 에서 두 단계 위 → shared).
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))

from blackbox import Cli, resolve_target_module, resolve_target_root  # noqa: E402

MODULE_CANDIDATES = ("budget_app", "budgetapp", "ledger", "household_ledger", "account_book")
CSV_HEADER = "date,type,category,amount,memo,tags"
SEED_CSV = (
    CSV_HEADER
    + "\n"
    + "2024-01-15,expense,food,15000,lunchmemo,meal\n"
    + "2024-01-14,income,salary,3000000,paymemo,\n"
    + "2024-01-20,expense,rent,150000,rentmemo,fixed\n"
)


class SmokeFailure(AssertionError):
    """스모크 단계 실패 — 어느 단계가 왜 실패했는지 메시지에 담는다."""


def check(cond: bool, step: str, detail: str = "") -> None:
    if not cond:
        raise SmokeFailure(f"[{step}] 실패\n{detail}".rstrip())


def find_opt(help_text: str, candidates: list[str], step: str) -> str:
    for opt in candidates:
        if re.search(rf"(?<![\w-]){re.escape(opt)}(?![\w-])", help_text):
            return opt
    raise SmokeFailure(f"[{step}] 옵션을 help 에서 찾지 못했습니다: {candidates}\n{help_text}")


def smoke(cli: Cli, workdir: Path) -> None:
    # 1) 실행 가능성 — help
    check(cli.run("--help").returncode == 0, "help", cli.output(cli.run("--help")))

    # 2) import — 거래 3건 적재
    csv_path = workdir / "seed.csv"
    csv_path.write_text(SEED_CSV, encoding="utf-8")
    from_opt = find_opt(cli.help_of("import"), ["--from", "--file", "--in"], "import")
    proc = cli.run("import", from_opt, str(csv_path))
    check(proc.returncode == 0, "import", cli.output(proc))

    # 3) list — 파일 영속성(별도 프로세스)
    proc = cli.run("list")
    check(proc.returncode == 0, "list", cli.output(proc))
    check("lunchmemo" in cli.output(proc), "list", cli.output(proc))

    # 4) summary — 합계
    m_opt = find_opt(cli.help_of("summary"), ["--month", "-m"], "summary")
    proc = cli.run("summary", m_opt, "2024-01")
    body = re.sub(r"(?<=\d),(?=\d)", "", cli.output(proc))  # 3,000,000 → 3000000
    check(proc.returncode == 0, "summary", body)
    check("3000000" in body, "summary", f"총 수입 3000000 이 없습니다:\n{body}")
    check("165000" in body, "summary", f"총 지출 165000 이 없습니다:\n{body}")

    # 5) export — CSV 왕복
    ehelp = cli.help_of("export")
    out_opt = find_opt(ehelp, ["--out", "--to", "--output"], "export")
    target = workdir / "out.csv"
    args = ["export", out_opt, str(target)]
    if re.search(r"(?<![\w-])--month(?![\w-])", ehelp):
        args += ["--month", "2024-01"]
    proc = cli.run(*args)
    check(proc.returncode == 0, "export", cli.output(proc))
    check(target.exists(), "export", f"출력 파일이 없습니다: {target}")
    rows = list(csv.DictReader(io.StringIO(target.read_text(encoding="utf-8"))))
    check(len(rows) == 3, "export", f"import 3건 → export {len(rows)}건 (불일치)")

    # 6) 오류 처리 — 0이 아닌 종료 코드 + 스택트레이스 미노출
    proc = cli.run("summary", m_opt, "2024-13")
    out = cli.output(proc)
    check(proc.returncode != 0, "error-handling", f"잘못된 월인데 종료 코드가 0입니다:\n{out}")
    check(
        "Traceback (most recent call last)" not in out,
        "error-handling",
        f"스택트레이스가 노출되었습니다:\n{out}",
    )


def main() -> int:
    root = resolve_target_root()
    module = resolve_target_module(root, MODULE_CANDIDATES)
    print(f"[i] 대상: {root}  (모듈: {module})")
    with tempfile.TemporaryDirectory(prefix="budget_smoke_") as tmp:
        workdir = Path(tmp)
        cli = Cli(root, module, workdir)
        try:
            smoke(cli, workdir)
        except SmokeFailure as exc:
            print(f"[FAIL] 스모크 테스트 실패\n{exc}")
            return 1
        except subprocess.TimeoutExpired:
            print("[FAIL] 명령이 응답하지 않습니다(대화형 입력 대기 가능성).")
            return 1
    print("[OK] 스모크 통과 — help/import/list/summary/export/오류처리 정상")
    return 0


if __name__ == "__main__":
    sys.exit(main())
