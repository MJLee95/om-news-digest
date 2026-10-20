# Daily Clippings

매일 아침 sustainable operations, ESG, supply chain resilience, energy/AI 데이터센터, circular economy 등 관련 뉴스 5개를 골라, 기사마다 **문제 구조(배경 · 문제 · 어디서 왜 · 이해당사자)와 연구 힌트**를 붙여 Gmail로 보내주는 개인 연구용 뉴스레터입니다. 지난 기사는 아카이브 사이트에 쌓입니다.

- 📰 **아카이브:** https://mjlee95.github.io/om-news-digest/
- ℹ️ **About:** https://mjlee95.github.io/om-news-digest/about.html

## 작동 방식

```
RSS 14곳 + Google News 검색 16개 + Crossref(새 논문)
        │  최근 36시간, 이미 보낸 기사·중복 제외 (하루 약 200~280개 후보)
        ▼
① Claude: 후보 중 5개 + Also worth noting 5개 선정
   (테마 분산, 같은 사건 중복 제거, 후속 기사 연결, ★ 별표 반영)
② Claude + 웹 검색: 원문을 찾아 사실 확인 → 리서치 노트
③ OpenAlex: 기사별 관련 논문 검색 (실제 논문 중에서만 선택)
④ Claude: 노트만 근거로 작성 (요약, 문제 구조, 연구 힌트, 데이터 단서)
        ▼
Gmail 발송 → 스토리 브리핑 갱신 → 아카이브 사이트(docs/) 재생성 → GitHub에 커밋
```

**실행 시각:** cron-job.org가 매일 06:15 ET(주간 리뷰는 일요일 09:00 ET)에 GitHub Actions를 실행합니다. GitHub 자체 예약(06:17, 07:47 ET)은 예비용입니다. 그날 이미 보냈으면 메일 없이 바로 끝나므로 중복 발송은 없습니다.

## 주요 기능

**매일 메일**
- 주요 기사 5개. 기사마다 요약 · Background · Problem · Where & why · Stakeholders · Research hints(1~3개) · Data leads · Keywords · Related research가 들어갑니다.
- Thread to pull(오늘 기사들 사이의 연결), Also worth noting(제목+링크 5개), New in the journals(MS·M&SOM·POM·JOM 새 논문)
- 메일 제목에 날짜가 들어갑니다.

**주간 리뷰 (일요일)**
- 한 주 기사를 다시 읽고 구체화한 연구 아이디어 2~3개(질문 · 왜 지금 · 데이터 · 식별 전략과 위협 · 문헌), 패턴, 진행 중인 이야기, 다음 주에 지켜볼 것, 데이터셋 후보를 보내줍니다.
- 미리 보기: `python run_weekly.py --dry-run`

**스토리 브리핑**
- 같은 사건의 후속 기사가 이어지면 Story threads 탭에 사건 브리핑 페이지가 생깁니다(배경, 원인, 관련 주체와 이해관계, 현재 상황, 지켜볼 것, 연구 관점, 출처).
- 새 기사가 붙을 때마다 브리핑은 최신으로 다시 쓰이고, 바뀐 내용은 업데이트 기록에 쌓이며, 이전 브리핑은 페이지 아래에 보관됩니다.
- 수동 갱신: `python -m digest.threads`

**아카이브 사이트**
- 달력(날짜·월 단위 보기), 페이지 나누기(5/7/10개), 검색
- 테마(1개)와 키워드(여러 개, 모두 포함) 필터. 고를 때마다 남은 기사에 있는 태그만 보입니다.
- 탭: Issues · Story threads · Datasets · ★ Starred · Weekly reviews
- 라이트/다크/시스템 테마 전환, About 페이지, GoatCounter 방문 통계(쿠키 없음)

**★ 별표**
- 아카이브에서 ☆를 누르면 별표, ★를 누르면 해제됩니다. 메일의 ☆ Star 링크는 아카이브를 열어 별표를 답니다.
- 브라우저마다 처음 한 번 GitHub 토큰(이 저장소 Issues 읽기/쓰기만)을 연결합니다. 토큰은 그 브라우저에만 저장됩니다.
- ★ Starred 탭에서 메모를 달 수 있고, 별표와 메모는 다음 날부터 기사 선정과 주간 리뷰에 반영됩니다.

**데이터셋 목록**
- `datasets.yaml`(46개, 분야 · 접근성 · 링크 · 무료 대안)에 있는 데이터만 기사당 최대 2개 연결되어 Datasets 탭에 분야별로 쌓입니다.
- 목록에 없는 데이터는 '후보'로만 기록되고, 2회 이상 언급되면 주간 리뷰에 나옵니다. 쓸 만한 후보는 `datasets.yaml`에 직접 추가하세요.

**실패 알림**
- 실행이 실패하면 "⚠️ ... failed" 메일이 로그 링크와 함께 옵니다. Gmail 설정 자체가 문제인 경우에는 GitHub가 계정 이메일로 알려줍니다.

## 고치는 곳

| 바꾸고 싶은 것 | 파일 |
|---|---|
| 관심사, 기사 개수, 테마, 뉴스 소스, 학술지, 바이라인 | `config.yaml` |
| 데이터셋 목록과 접근성 | `datasets.yaml` |
| About 페이지 | `about.md` |
| 실행 시각 | cron-job.org (예비: `.github/workflows/*.yml`의 cron) |

`about.md`, `config.yaml`, `datasets.yaml`을 GitHub에서 고치면 1~2분 안에 사이트가 자동으로 다시 만들어집니다(비용 없음).

## 설정 (처음 한 번)

1. **Anthropic API 키**: https://console.anthropic.com → API Keys. Claude 구독과 별개인 종량제입니다. 매일 실행은 회당 $0.7~0.9, 주간 리뷰는 약 $0.1, 스토리 브리핑은 갱신될 때마다 $0.3~0.7입니다.
2. **Gmail 앱 비밀번호**: 2단계 인증을 켠 뒤 https://myaccount.google.com/apppasswords 에서 만듭니다.
3. **GitHub Secrets** (Settings → Secrets and variables → Actions): `ANTHROPIC_API_KEY`, `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `DIGEST_RECIPIENT`. 로컬 `.env`가 있으면 `gh secret set -f .env`로 한 번에 등록됩니다.
4. **cron-job.org**: `POST https://api.github.com/repos/MJLee95/om-news-digest/actions/workflows/daily.yml/dispatches`, 헤더 `Authorization: Bearer <Actions 쓰기 권한 토큰>` · `Accept: application/vnd.github+json` · `X-GitHub-Api-Version: 2022-11-28`, 본문 `{"ref":"main"}`. 주간 리뷰는 `weekly.yml`로 하나 더 만듭니다. 토큰 만료일: 2027-10-14.

### 로컬에서 실행
```bash
cd ~/Projects/om-news-digest
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
cp .env.example .env                          # 값 채우기
./.venv/bin/python run.py --candidates-only   # 후보만 확인 (무료)
./.venv/bin/python run.py --dry-run           # 메일 없이 output/preview.html 생성
./.venv/bin/python -m digest.archive          # 아카이브 사이트만 다시 만들기
```
iCloud "Mac 저장 공간 최적화"가 켜진 데스크탑·문서 폴더에 두면 파일이 클라우드로 옮겨져 읽기가 멈출 수 있습니다. iCloud 동기화 밖(예: `~/Projects`)에 두세요.

## 데이터 파일

- `data/issues/`: 날짜별 뉴스레터 원본(HTML, JSON)
- `data/threads/`: 스토리 브리핑(현재 버전, 업데이트 기록, 이전 버전)
- `data/weekly/`: 주간 리뷰
- `data/archive.csv`: 지금까지 보낸 모든 기사 (엑셀·pandas 분석용)
- `data/dataset_candidates.json`: 목록에 없는 데이터셋 후보

## 변경 기록

### 2026-10-19
- **기사 형식 변경:** "OM angle / Research Q / Data / ID" 대신 **Background · Problem · Where & why · Stakeholders · Research hints(1~3개) · Data leads**. 완성된 연구 질문 대신 문제 구조와 힌트를 주는 방식입니다. Thread to pull도 "탐색해볼 연결" 수준으로 바꿨습니다. 이전 기사는 예전 형식 그대로 둡니다.
- **스토리 브리핑 페이지 추가:** 스레드마다 5W1H 브리핑(배경, 원인, 관련 주체와 이해관계, 현재 상황, 지켜볼 것, 연구 관점, 출처). 갱신 시 현재 브리핑은 다시 쓰고, 업데이트 기록은 쌓고, 이전 버전은 보관합니다. 첫 브리핑: "PJM data center load, curtailment rules and resource adequacy"
- 후속 기사 연결 기준 강화: 같은 구체적 사건(같은 절차·규칙·프로젝트·분쟁)만 연결하고, 브리핑 단계에서 다른 사건으로 판단된 기사는 스레드에서 뺍니다.
- 로컬 작업 폴더를 `~/Projects/om-news-digest`로 옮겼습니다(iCloud 데스크탑 동기화 문제).

### 2026-10-15
- **실행 방식 변경:** 이 저장소에서는 GitHub 예약 실행이 몇 시간씩 늦어서, cron-job.org가 GitHub Actions를 직접 실행하도록 바꿨습니다(매일 06:15 ET).
- 주간 리뷰에도 "이번 주에 이미 보냈으면 건너뛰기"를 추가했습니다.

### 2026-10-14
- 중복 발송 방지(그날 이미 보냈으면 건너뛰기)와 예비 실행 시각(07:47 ET) 추가
- **About 페이지 추가** (`about.md`)
- `about.md`·`config.yaml`·`datasets.yaml`을 고치면 사이트가 자동으로 다시 만들어지는 Rebuild site 작업 추가
- GitHub 예약이 실행되지 않아 첫 정기 메일은 수동으로 실행했습니다.

### 2026-10-13: 프로젝트 시작
- **첫 버전:** RSS·Google News 수집 → Claude 선정·사실 확인·작성 → Gmail 발송 → GitHub Actions 매일 실행 → GitHub Pages 아카이브
- 이름을 "OM Research Radar"에서 **"Daily Clippings"**로 변경
- 기사별 관련 논문(OpenAlex 검색 결과 중에서만 선택), 매일 새 논문 섹션
- 테마 10개로 고정, Also worth noting 섹션 추가, 메일 하단 문구 버그 수정
- **아카이브 기능:** 날짜별 타임라인, 테마·키워드 태그, 검색, 접고 펴기, 라이트/다크/시스템 전환, 달력, 페이지 나누기, 다중 키워드 필터
- **후속 기사 연결(Story threads), 데이터셋 모음, ★ 별표, 주간 리뷰, 실패 알림** 추가. 메일 제목에 날짜를 넣었습니다.
- 데이터셋을 기준 목록(`datasets.yaml`, 접근성 표시) 방식으로 정리하고, 목록 밖 데이터는 후보로만 기록
- ★ 별표를 한 번 클릭으로 달고 해제할 수 있게 변경(GitHub API)
- 웹 검색 단계에 캐싱을 적용해 회당 비용을 약 $2.1에서 $0.7로 줄였습니다.
- 바이라인("A personal project by Minjae Lee · UMD Smith"), GoatCounter 방문 통계(쿠키 없음, 본인 방문 제외 지원)
