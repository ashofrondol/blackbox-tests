# blackbox-tests

codyssey 과제들을 **블랙박스 · 구현 비의존** 방식으로 채점하는 그레이더 저장소.

- 대상 앱을 `python -m <module>` **서브프로세스로만** 구동한다 → 내부 코드/구조가 달라도 통과.
- 대상은 `TARGET_ROOT` / `TARGET_MODULE` **환경변수**로 지정한다 (`grade.sh` 가 세팅).
- 옵션명(`--from`/`--file` …)은 `--help` 출력에서 **자동 탐지** → 옵션 이름이 달라도 대응.
- 사람이 읽는 **문구는 단언하지 않는다**. 명세가 고정한 것(종료 코드/저장 파일/CSV 스키마)만 본다.

> 이 저장소는 **DevEnvAuto/dev-env-bootstrap 의 바로 위 상위 폴더(= `DevEnvAuto/`)** 에
> `blackbox-tests` 라는 이름으로 두면, dev-env-bootstrap 이 자동 발견해 `make grade` 로 실행한다.

## 폴더 구조

```
blackbox-tests/
├── pyproject.toml            # pytest + import-mode=importlib + pythonpath=[shared]
├── grade.sh                  # 한 구현체 × 한 과제 채점
├── grade_all.sh              # 여러 제출물 일괄 채점 (요약표 + 로그)
├── shared/
│   └── blackbox.py           # 공용 하네스: Cli 러너 · 옵션 탐지 · 단언 · TestCase 파서
└── assignments/
    └── b2_1_budget_app/      # 과제 1개 = 자기완결 테스트 패키지
        ├── assignment.toml   # 메타데이터(제목/모듈 후보)
        ├── conftest.py       # 이 과제 픽스처(대상 해석·시드 CSV)
        ├── TestCase.txt      # 종료 코드 계약 (<인자> => <코드>)
        ├── smoke_test.py     # pytest 없이 도는 핵심 경로 점검
        └── test_contract.py  # 블랙박스 계약 테스트 (contract / optional 마커)
```

## 사전 준비 (최초 1회)

```bash
uv sync            # pytest 등 dev 의존성 설치
```

DevEnvAuto 를 쓴다면 `dev-env-bootstrap` 에서 `make setup` 으로 `uv` 를 먼저 깔아둔다.

## 사용법

### 내 과제 채점

```bash
./grade.sh ~/Desktop/codyssey_B2-1
```

### 남의 과제 채점 (같은 명세, 다른 구현)

```bash
./grade.sh ~/classmates/kim                        # 모듈명 자동탐지(__main__.py)
./grade.sh ~/classmates/lee b2_1_budget_app my_app  # 모듈명 직접 지정
```

### 여러 제출물 일괄 채점

```bash
./grade_all.sh ~/submissions            # ~/submissions/<사람>/ 마다 채점
# 요약표가 출력되고, 실패 상세는 reports/b2_1_budget_app/<사람>.log 에 남는다
```

### dev-env-bootstrap 을 통해 실행 (자동 발견)

```bash
cd ../dev-env-bootstrap
make grade-detect                       # 그레이더 발견 여부 확인
make grade TARGET=~/Desktop/codyssey_B2-1
make grade TARGET=~/classmates/kim ASSIGNMENT=b2_1_budget_app MODULE=my_app
```

## 왜 구현이 달라도 통과하나

| 구현마다 다른 것 | 흡수 방법 |
| --- | --- |
| 모듈/패키지 이름 | `TARGET_MODULE` 또는 `__main__.py` 자동탐지 |
| 옵션 이름 (`--from`/`--file`) | `--help` 출력에서 후보 중 존재하는 것을 탐지 |
| 출력 문구/서식 | 단언하지 않음. 종료 코드·저장 파일·CSV 스키마만 검증 |
| 금액 표기 (`3,000,000`) | 비교 전 콤마 제거로 정규화 |
| 내부 구조/클래스 | 아예 import 하지 않음(서브프로세스 블랙박스) |

## 새 과제 추가하기

1. `assignments/b2_1_budget_app/` 를 통째로 복사해 `assignments/<새과제ID>/` 로 만든다.
2. `assignment.toml` 의 제목/모듈 후보, `conftest.py` 의 `MODULE_CANDIDATES`·시드 데이터,
   `TestCase.txt`·`test_contract.py` 를 그 과제 명세에 맞게 고친다.
3. 공용 로직(서브프로세스 실행·옵션 탐지·단언)은 `shared/blackbox.py` 를 그대로 재사용한다.
4. `./grade.sh <대상> <새과제ID>` 로 실행. 과제별 `conftest.py` 는 서로 격리된다
   (`--import-mode=importlib`).

## 마커

- `contract` — 명세가 요구하는 필수 계약. **어떤 구현이든 통과해야 한다.**
- `optional` — 구현마다 다를 수 있는 확장. 미지원이면 skip.

```bash
uv run pytest assignments/b2_1_budget_app -m contract   # 필수만
```
