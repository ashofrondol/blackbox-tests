"""그레이더 루트 conftest — 채점 결과를 Markdown 보고서로 남기는 리포트 플러그인.

환경변수 ``GRADE_REPORT`` 에 출력 경로가 지정되면(=grade.sh 가 설정), 세션이 끝날 때
그 경로에 '무엇이 문제인지' 중심의 보고서를 쓴다. 지정이 없으면 아무 것도 하지 않는다.

- 실패(failed): 명세 위반 → 무엇을 검사했는지(docstring) + 왜 실패했는지(assert 메시지)
- 건너뜀(skipped): optional 미지원/전제 미충족 → 이유
- 통과(passed): 요약만

과제별 conftest/fixture 와 독립적으로 동작한다(--import-mode=importlib 로 이름 충돌 없음).
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

_results: list[dict] = []
_docstrings: dict[str, str] = {}


def pytest_itemcollected(item) -> None:
    fn = getattr(item, "function", None)
    doc = ""
    if fn is not None and fn.__doc__:
        doc = fn.__doc__.strip().splitlines()[0].strip()
    _docstrings[item.nodeid] = doc


def pytest_runtest_logreport(report) -> None:
    # call 단계 결과, 또는 setup 단계의 skip/error 만 기록(중복 없이).
    if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
        _record(report)


def _record(report) -> None:
    kw = report.keywords
    marker = "contract" if "contract" in kw else ("optional" if "optional" in kw else "-")
    reason = ""
    if report.skipped:
        lr = report.longrepr
        reason = lr[2] if isinstance(lr, tuple) and len(lr) == 3 else report.longreprtext
        reason = reason.replace("Skipped: ", "").strip()
    elif report.failed:
        reason = report.longreprtext
    _results.append(
        {
            "name": report.nodeid.split("::", 1)[-1],
            "outcome": report.outcome,  # passed | failed | skipped
            "marker": marker,
            "reason": reason,
            "doc": _docstrings.get(report.nodeid, ""),
        }
    )


def _assert_lines(text: str) -> str:
    """pytest 실패 repr 에서 assert 메시지('E ' 로 시작하는 줄)만 뽑는다."""
    lines = [ln.lstrip()[1:].strip() for ln in text.splitlines() if ln.lstrip().startswith("E ")]
    return "\n".join(lines) if lines else text.strip()[-1500:]


def pytest_sessionfinish(session, exitstatus) -> None:
    out = os.environ.get("GRADE_REPORT", "").strip()
    if not out:
        return
    try:
        _write_report(Path(out))
    except Exception as exc:  # 보고서 실패가 채점 자체를 막지 않도록
        print(f"[report] 보고서 작성 실패: {exc}")


def _write_report(path: Path) -> None:
    failed = [r for r in _results if r["outcome"] == "failed"]
    skipped = [r for r in _results if r["outcome"] == "skipped"]
    passed = [r for r in _results if r["outcome"] == "passed"]
    total = len(_results)
    verdict = "PASS" if not failed else "FAIL"

    target = os.environ.get("TARGET_ROOT", "(미지정)")
    module = os.environ.get("TARGET_MODULE", "(자동탐지)")
    assignment = os.environ.get("GRADE_ASSIGNMENT", "b2_1_budget_app")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    md: list[str] = []
    md.append(f"# 채점 보고서 — {assignment}\n")
    md.append("| 항목 | 값 |")
    md.append("| --- | --- |")
    md.append(f"| 대상 | `{target}` |")
    md.append(f"| 모듈 | `{module}` |")
    md.append(f"| 일시 | {now} |")
    md.append(f"| 판정 | **{verdict}** |")
    md.append(f"| 집계 | 통과 {len(passed)} · 실패 {len(failed)} · 건너뜀 {len(skipped)} (총 {total}) |")
    md.append("")

    # ---------- 실패(문제) ----------
    if failed:
        md.append("## ❌ 실패 — 고쳐야 할 문제\n")
        md.append("각 항목은 *무엇을 검사했는지*와 *왜 실패했는지*를 함께 보여준다.\n")
        for r in failed:
            tag = "필수" if r["marker"] == "contract" else r["marker"]
            md.append(f"### `{r['name']}`  ({tag})")
            if r["doc"]:
                md.append(f"> {r['doc']}")
            md.append("")
            md.append("```")
            md.append(_assert_lines(r["reason"]) or "(메시지 없음)")
            md.append("```")
            md.append("<details><summary>상세 로그</summary>\n")
            md.append("```")
            md.append((r["reason"] or "").strip()[:3000] or "(없음)")
            md.append("```")
            md.append("</details>\n")
    else:
        md.append("## ✅ 실패한 필수 계약 없음\n")

    # ---------- 건너뜀 ----------
    if skipped:
        md.append("## ⏭️ 건너뜀 — optional 미지원 또는 전제 미충족\n")
        for r in skipped:
            md.append(f"- `{r['name']}` ({r['marker']}) — {r['reason'] or '이유 미상'}")
        md.append("")

    # ---------- 통과 요약 ----------
    if passed:
        md.append(f"## ✅ 통과 ({len(passed)}건)\n")
        md.append("<details><summary>펼치기</summary>\n")
        for r in passed:
            md.append(f"- `{r['name']}`")
        md.append("\n</details>")
        md.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(md) + "\n", encoding="utf-8")
