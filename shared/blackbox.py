"""구현 비의존 블랙박스 테스트용 공용 하네스.

모든 과제(assignments/*)가 이 모듈을 재사용한다. 특정 구현/과제에 묶이지 않도록
다음 원칙을 강제한다.

1. **블랙박스 실행**: 내부 함수를 import 하지 않고 ``python -m <module>`` 서브프로세스로
   구동한다. 모듈/클래스 이름 등 내부 구조가 달라도 통과한다.
2. **cwd 격리**: 각 테스트는 임시 디렉터리에서 실행한다. 앱의 기본 데이터 폴더
   (``./data`` 등)가 그 안에 생기므로 상태가 서로 섞이지 않는다.
3. **옵션명 자동 탐지**: ``--from`` / ``--file`` 처럼 구현마다 다를 수 있는 옵션은
   ``--help`` 출력에서 찾아 쓴다. 못 찾으면 skip.
4. **느슨한 단언**: 사람이 읽는 문구는 구현마다 다르므로 비교하지 않는다. 대신
   명세가 고정한 것(종료 코드/저장 파일/CSV 스키마)만 단언한다.

대상 지정(환경변수):
    TARGET_ROOT   : 채점할 프로젝트 루트 (필수)
    TARGET_MODULE : ``python -m <module>`` 모듈명 (없으면 후보/__main__.py 로 자동탐지)
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

# 서브프로세스 1회 실행 상한(초) — 대화형 명령이 입력을 기다리며 멈추는 것을 방지.
CLI_TIMEOUT = 60

# 자동탐지에서 모듈로 오인하면 안 되는 디렉터리 이름
_NON_MODULE_DIRS = {"tests", "test", ".venv", "venv", "__pycache__", ".git", "data"}


# ---------- 대상 프로젝트/모듈 해석 ----------


def resolve_target_root() -> Path:
    env = os.environ.get("TARGET_ROOT", "").strip()
    if not env:
        raise RuntimeError(
            "TARGET_ROOT 환경변수가 필요합니다 (채점 대상 프로젝트 경로). "
            "grade.sh 를 통해 실행하면 자동으로 설정됩니다."
        )
    return Path(env).expanduser().resolve()


def discover_module(root: Path, candidates: Sequence[str] = ()) -> Optional[str]:
    """대상 루트에서 ``python -m`` 으로 실행 가능한 모듈명을 찾는다.

    1) candidates 중 ``<root>/<name>/__main__.py`` 가 있는 첫 이름
    2) 없으면 ``<root>/*/__main__.py`` 를 스캔한 첫 패키지 (tests/.venv 등 제외)
    """
    for name in candidates:
        if (root / name / "__main__.py").is_file():
            return name
    for main in sorted(root.glob("*/__main__.py")):
        pkg = main.parent.name
        if pkg not in _NON_MODULE_DIRS:
            return pkg
    return None


def resolve_target_module(root: Path, candidates: Sequence[str] = ()) -> str:
    env = os.environ.get("TARGET_MODULE", "").strip()
    if env:
        return env
    mod = discover_module(root, candidates)
    if not mod:
        raise RuntimeError(
            f"모듈 자동탐지 실패: {root} 아래에서 __main__.py 를 찾지 못했습니다. "
            "TARGET_MODULE 환경변수(또는 grade.sh 세 번째 인자)로 모듈명을 지정하세요."
        )
    return mod


# ---------- CLI 러너 ----------


class Cli:
    """대상 앱을 서브프로세스로 실행하는 얇은 래퍼(내부 코드를 import 하지 않는다)."""

    def __init__(self, root: Path, module: str, workdir: Path):
        self.root = root
        self.module = module
        self.workdir = workdir

    def run(
        self,
        *args: str,
        stdin: Optional[str] = None,
        cwd: Optional[Path] = None,
        timeout: int = CLI_TIMEOUT,
    ) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        # 대상 루트를 import 경로에 얹어 `python -m <module>` 이 어디서든 동작하게 한다.
        env["PYTHONPATH"] = os.pathsep.join(
            [str(self.root), env.get("PYTHONPATH", "")]
        ).rstrip(os.pathsep)
        # 콘솔 코드페이지 때문에 한글 출력이 깨지지 않도록 강제한다.
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        return subprocess.run(
            [sys.executable, "-m", self.module, *args],
            cwd=str(cwd or self.workdir),
            env=env,
            input=stdin if stdin is not None else "",
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )

    def output(self, proc: subprocess.CompletedProcess) -> str:
        return (proc.stdout or "") + (proc.stderr or "")

    def help_of(self, *args: str) -> str:
        """``<args> --help`` 출력을 반환(실패해도 빈 문자열)."""
        return self.output(self.run(*args, "--help"))

    @property
    def data_dir(self) -> Path:
        return self.workdir / "data"


# ---------- 옵션명 자동 탐지 ----------


def discover_option(help_text: str, candidates: Sequence[str]) -> Optional[str]:
    """help 출력에서 후보 옵션 중 실제 존재하는 것을 찾아 반환(없으면 None).

    단어 경계로 매칭하여 ``--to`` 가 ``--total`` 에 잘못 걸리지 않게 한다.
    """
    for opt in candidates:
        if re.search(rf"(?<![\w-]){re.escape(opt)}(?![\w-])", help_text):
            return opt
    return None


def require_option(help_text: str, candidates: Sequence[str], what: str) -> str:
    """옵션을 못 찾으면 pytest.skip (특정 구현에 테스트를 고정하지 않기 위함)."""
    opt = discover_option(help_text, candidates)
    if opt is None:
        import pytest

        pytest.skip(f"{what} 옵션을 help 에서 찾지 못했습니다 (후보: {list(candidates)})")
    return opt


# ---------- 공용 단언/헬퍼 ----------


def assert_no_traceback(output: str) -> None:
    """스택트레이스가 사용자 출력에 노출되지 않아야 한다."""
    assert "Traceback (most recent call last)" not in output, (
        "스택트레이스가 사용자 출력에 노출되었습니다:\n" + output[:1000]
    )


def data_files(data_root: Path) -> List[Path]:
    """데이터 폴더에서 앱이 만든 저장 파일 목록(형식 불문)."""
    if not data_root.is_dir():
        return []
    return sorted(p for p in data_root.rglob("*") if p.is_file())


def write_csv(path: Path, rows: Sequence[str], header: str) -> Path:
    """UTF-8(BOM 없음) CSV 를 만든다. rows 는 헤더를 제외한 줄 목록."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")
    return path


def load_testcases(path: Path) -> List[Tuple[List[str], str]]:
    """``<인자...> => <기대 종료코드>`` 계약 파일을 (args, expected) 목록으로 읽는다.

    - ``#`` 로 시작하거나 빈 줄, ``=>`` 없는 줄은 무시.
    - ``!0`` 은 "0이 아닌 값"을 뜻한다(테스트에서 해석).
    """
    cases: List[Tuple[List[str], str]] = []
    path = Path(path)
    if not path.exists():
        return cases
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=>" not in line:
            continue
        left, expected = line.split("=>", 1)
        args = shlex.split(left.strip())
        if not args:
            continue
        cases.append((args, expected.strip()))
    return cases
