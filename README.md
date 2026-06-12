# Journal Alert

지정한 저널에서 매일 새 논문을 검색하고, 의료영상 AI 연구만 골라 Slack으로 알려주는 논문 알리미입니다. 검색 결과는 Excel 데이터베이스와 LLM이 읽기 쉬운 Markdown 표에 함께 누적됩니다.

현재 누적된 논문 DB는 [`data/paper_database.md`](data/paper_database.md)에서 확인할 수 있습니다.

## 구현 목적

매일 오전 9시에 아래 조건에 맞는 논문을 자동으로 조사합니다.

- 대상 모달리티: Mammography, Chest X-ray, Breast MRI
- 대상 방법론: Deep learning, Machine learning, Generative AI
- 대상 저널: NCS 본지 및 Nature 계열 주요 자매지, Medical Image Analysis, IEEE Transactions on Medical Imaging
- 알림 방식: Slack Incoming Webhook
- 저장 방식: Excel + Markdown 동시 누적

## 현재 조사 저널

NCS 및 Nature 계열로는 아래 저널을 조사합니다.

| 구분 | 저널 |
| --- | --- |
| NCS 본지 | Nature Computational Science |
| Nature 계열 | Nature Machine Intelligence |
| Nature 계열 | Nature Medicine |
| Nature 계열 | Nature Biomedical Engineering |
| Nature 계열 | Nature Communications |
| Nature 계열 | npj Digital Medicine |

의료영상 전문 저널로는 아래 저널을 함께 조사합니다.

| 구분 | 저널 |
| --- | --- |
| Medical imaging | Medical Image Analysis |
| Medical imaging | IEEE Transactions on Medical Imaging |

저널 목록은 `config/journals.yml`에서 관리합니다. ISSN이 등록된 저널은 Crossref에서 ISSN 기반으로 검색해 저널명 오인식을 줄입니다.

## 주요 기능

- Crossref API 기반 논문 검색
- Crossref에 abstract가 없을 때 출판사 페이지 직접 파싱
- 날짜 범위 지정 검색
- 긴 기간 검색을 위한 Crossref cursor pagination 지원
- 저널별 최대 확인 개수 지정
- 모달리티 및 AI 방법론 키워드 필터링
- DOI 기준 중복 제거
- Excel 데이터베이스 누적 저장
- Markdown 표 자동 생성
- Slack 알림 발송
- 매일 오전 9시 실행용 로컬 스케줄러
- Windows 작업 스케줄러 등록 가능

직접 abstract 파싱은 출판사 타입별로 분리되어 있습니다.

| 타입 | 대상 |
| --- | --- |
| Nature | `nature.com`, Nature 계열, npj 계열 |
| IEEE | IEEE Xplore, IEEE DOI |
| Elsevier | ScienceDirect, Elsevier DOI, Medical Image Analysis |
| PubMed | DOI 기반 NCBI E-utilities fallback |
| Generic | 표준 citation/meta description fallback |

## 폴더 구조

```text
journal-alert/
├─ config/
│  └─ journals.yml
├─ data/
│  ├─ paper_database.xlsx
│  └─ paper_database.md
├─ src/
│  └─ slack_paper_alert/
│     ├─ abstract_fetchers.py
│     ├─ cli.py
│     ├─ config.py
│     ├─ job.py
│     ├─ models.py
│     ├─ scheduler.py
│     ├─ search.py
│     ├─ slack.py
│     └─ store.py
├─ .env.example
├─ requirements.txt
└─ run.py
```

## 설치

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

`.env`에 Slack Incoming Webhook URL을 입력합니다.

```text
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
SLACK_CHANNEL=
SLACK_USERNAME=paper-alert-bot
SLACK_ICON_EMOJI=:newspaper:
```

`SLACK_CHANNEL`은 Incoming Webhook 설정에 채널이 고정되어 있다면 비워둬도 됩니다.

## 실행 방법

Slack 발송 없이 최근 3일치만 테스트합니다.

```powershell
python run.py run-once --days-back 3 --no-slack
```

Slack 알림까지 포함해 1회 실행합니다.

```powershell
python run.py run-once --days-back 1
```

특정 기간만 조사합니다.

```powershell
python run.py run-once --from-date 2026-05-01 --to-date 2026-06-12 --no-slack
```

긴 기간을 깊게 조사합니다.

```powershell
python run.py run-once --from-date 2026-01-01 --to-date 2026-06-12 --max-rows-per-journal 5000 --no-slack
```

이미 저장된 논문 중 비어 있는 abstract를 출판사 페이지에서 직접 다시 가져옵니다.

```powershell
python run.py refresh-abstracts
```

이미 들어간 abstract도 더 긴 직접 파싱 결과가 있으면 갱신합니다.

```powershell
python run.py refresh-abstracts --force
```

## 매일 오전 9시 실행

로컬 프로세스로 계속 실행하려면 아래 명령을 사용합니다. 기본 timezone은 `Asia/Seoul`입니다.

```powershell
python run.py serve
```

Windows 작업 스케줄러에 등록하려면 아래 예시를 사용합니다.

```powershell
$Project = "C:\Users\MSI\Desktop\nj\Project\HS\slack_paper_alert"
$Python = "$Project\.venv\Scripts\python.exe"
$Action = New-ScheduledTaskAction -Execute $Python -Argument "run.py run-once" -WorkingDirectory $Project
$Trigger = New-ScheduledTaskTrigger -Daily -At 9:00AM
Register-ScheduledTask -TaskName "JournalAlert" -Action $Action -Trigger $Trigger -Description "Daily journal paper search and Slack alert" -User $env:USERNAME
```

## 저장 결과

검색 결과는 아래 두 파일에 누적됩니다.

- `data/paper_database.xlsx`
- `data/paper_database.md`

Excel에는 전체 필드를 저장하고, Markdown에는 LLM이 빠르게 읽을 수 있도록 핵심 컬럼만 표로 정리합니다.

저장 컬럼은 아래와 같습니다.

| 컬럼 | 설명 |
| --- | --- |
| discovered_date | 알리미가 발견한 날짜 |
| published_date | 논문 출판일 |
| journal | 저널명 |
| modality | Mammography, Chest X-ray, Breast MRI |
| method_family | Deep learning, Machine learning, Generative AI |
| title | 논문 제목 |
| authors | 저자 |
| doi | DOI |
| url | 논문 URL |
| abstract | 초록 |
| source_api | 검색 API |
| source_journal_config | 설정 파일 기준 저널명 |

## 2026년 백필 결과

2026-01-01부터 2026-06-12까지 조사한 결과, 조건에 맞는 논문 7건이 데이터베이스에 저장되었습니다.

| 모달리티 | 건수 |
| --- | ---: |
| Mammography | 1 |
| Chest X-ray | 5 |
| Breast MRI | 1 |

현재까지 결과는 `data/paper_database.xlsx`와 `data/paper_database.md`에서 확인할 수 있습니다.

## 설정 변경

저널을 추가하거나 제외하려면 `config/journals.yml`을 수정합니다.

키워드를 조정하려면 `src/slack_paper_alert/search.py`의 아래 사전을 수정합니다.

- `MODALITY_TERMS`
- `METHOD_TERMS`

추천 확장 후보는 `Communications Medicine`, `npj Breast Cancer`, `Nature Methods`입니다. 다만 매일 Slack 알림 품질을 유지하려면 현재처럼 고신호 저널 위주로 운영하는 것을 기본값으로 둡니다.
