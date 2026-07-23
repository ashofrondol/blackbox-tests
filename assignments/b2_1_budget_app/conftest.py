"""B2-1 가계부(budget_app) 과제용 픽스처.

공용 하네스(``shared/blackbox.py`` — pytest 의 pythonpath 로 로드됨) 위에,
이 과제에만 해당하는 부분(CSV 스키마, 시드 데이터, 모듈명 후보)만 정의한다.

대상은 환경변수로 지정한다(``grade.sh`` 가 세팅):
    TARGET_ROOT    채점할 프로젝트 루트
    TARGET_MODULE  python -m <module> (없으면 MODULE_CANDIDATES 로 자동탐지)
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

import pytest
from blackbox import (  # shared/ (pyproject 의 pythonpath) 에서 로드
    Cli,
    require_option,
    resolve_target_module,
    resolve_target_root,
    write_csv,
)

# 이 과제에서 흔한 모듈명 후보 — 자동탐지에 사용(제출자마다 이름이 달라도 대응).
MODULE_CANDIDATES = (
    "budget_app",
    "budgetapp",
    "ledger",
    "household_ledger",
    "account_book",
)

# 과제 명세가 고정한 CSV
CSV_HEADER = "date,type,category,amount,memo,tags"
REQUIRED_CSV_COLUMNS = ("date", "type", "category", "amount")


@pytest.fixture(scope="session")
def target_root() -> Path:
    root = resolve_target_root()
    if not root.is_dir():
        pytest.exit(f"TARGET_ROOT 가 디렉터리가 아닙니다: {root}", returncode=4)
    return root


@pytest.fixture(scope="session")
def target_module(target_root: Path) -> str:
    return resolve_target_module(target_root, MODULE_CANDIDATES)


@pytest.fixture
def workdir(tmp_path: Path) -> Path:
    """테스트마다 격리된 작업 디렉터리 — 앱의 ``./data`` 가 여기에 생긴다."""
    d = tmp_path / "work"
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture
def cli(target_root: Path, target_module: str, workdir: Path) -> Cli:
    return Cli(target_root, target_module, workdir)


@pytest.fixture
def sample_csv(workdir: Path) -> Path:
    """정상 거래 3건(수입 1 + 지출 2)."""
    return write_csv(
        workdir / "seed.csv",
        [
            "2024-01-15,expense,food,15000,lunchmemo,meal",
            "2024-01-14,income,salary,3000000,paymemo,",
            "2024-01-20,expense,rent,150000,rentmemo,fixed",
        ],
        CSV_HEADER,
    )


@pytest.fixture
def seed(cli: Cli, sample_csv: Path):
    """대상 앱에 표준 거래 3건을 넣는다(비대화형 경로인 import 사용).

    반환: import 를 수행하는 호출 가능 객체. 실패 시 테스트를 skip 한다.
    """

    def _seed(csv_path: Optional[Path] = None) -> subprocess.CompletedProcess:
        from_opt = require_option(
            cli.help_of("import"), ["--from", "--file", "--in", "--input"], "import 입력"
        )
        proc = cli.run("import", from_opt, str(csv_path or sample_csv))
        if proc.returncode != 0:
            pytest.skip(f"import 로 데이터를 넣지 못해 건너뜁니다: {cli.output(proc)[:300]}")
        return proc

    return _seed
